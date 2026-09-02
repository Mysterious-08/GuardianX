from __future__ import annotations

from uuid import uuid4
from unittest.mock import patch

import httpx
import pytest

from app.agent.collectors.network import BidirectionalFlowAggregator
from app.agent.transport.events import (
    EventTransportError,
    SecurityEventTransport,
)


AGENT_ID = uuid4()
ACCESS_TOKEN = "test-access-token"


def completed_flow():
    aggregator = BidirectionalFlowAggregator()

    from app.agent.collectors.network import PacketObservation

    aggregator.observe(
        PacketObservation(
            timestamp=1.0,
            source_ip="10.0.0.1",
            source_port=4000,
            destination_ip="10.0.0.2",
            destination_port=443,
            protocol="TCP",
            byte_count=100,
        )
    )

    aggregator.observe(
        PacketObservation(
            timestamp=3.0,
            source_ip="10.0.0.2",
            source_port=443,
            destination_ip="10.0.0.1",
            destination_port=4000,
            protocol="TCP",
            byte_count=200,
        )
    )

    return aggregator.flush()[0]


def transport() -> SecurityEventTransport:
    return SecurityEventTransport(
        base_url="http://localhost:8000/",
        agent_id=AGENT_ID,
        access_token=ACCESS_TOKEN,
    )


def test_publish_posts_to_device_events_endpoint() -> None:
    record = completed_flow()

    response = httpx.Response(
        status_code=201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", transport().events_url),
    )

    with patch("app.agent.transport.events.httpx.post", return_value=response) as mock_post:
        transport().publish(record)

    mock_post.assert_called_once()

    call = mock_post.call_args
    assert call.args[0] == (
        f"http://localhost:8000/devices/{AGENT_ID}/events"
    )


def test_publish_sends_bearer_token_and_json_payload() -> None:
    record = completed_flow()

    response = httpx.Response(
        status_code=201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", transport().events_url),
    )

    with patch("app.agent.transport.events.httpx.post", return_value=response) as mock_post:
        transport().publish(record)

    kwargs = mock_post.call_args.kwargs

    assert kwargs["headers"]["Authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["headers"]["Accept"] == "application/json"

    payload = kwargs["json"]

    assert payload["event_type"] == "NETWORK"
    assert payload["severity"] == "INFO"
    assert payload["source"] == "guardianx.network_collector"
    assert payload["payload"]["schema_version"] == "draft-network-flow-v0"
    assert payload["payload"]["flow_duration"] == 2.0
    assert payload["payload"]["forward_packet_count"] == 1
    assert payload["payload"]["backward_packet_count"] == 1


def test_publish_uses_configured_timeout() -> None:
    record = completed_flow()

    response = httpx.Response(
        status_code=201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", transport().events_url),
    )

    client = SecurityEventTransport(
        base_url="http://localhost:8000",
        agent_id=AGENT_ID,
        access_token=ACCESS_TOKEN,
        timeout=7.5,
    )

    with patch("app.agent.transport.events.httpx.post", return_value=response) as mock_post:
        client.publish(record)

    assert mock_post.call_args.kwargs["timeout"] == 7.5


def test_publish_adds_ml_detection_payload() -> None:
    record = completed_flow()
    response = httpx.Response(
        status_code=201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", transport().events_url),
    )

    inference = type(
        "StubInference",
        (),
        {"predict": lambda self, vector: type("Result", (), {"prediction": 1, "anomaly_score": 0.018434047010596033})()},
    )()

    with patch("app.agent.transport.events.httpx.post", return_value=response) as mock_post:
        SecurityEventTransport(
            base_url="http://localhost:8000/",
            agent_id=AGENT_ID,
            access_token=ACCESS_TOKEN,
            inference=inference,
        ).publish(record)

    payload = mock_post.call_args.kwargs["json"]["payload"]
    vector = record.to_guardianx_v2_feature_vector()
    expected_features = {
        "flow_duration": vector[0],
        "forward_packet_count": vector[1],
        "backward_packet_count": vector[2],
        "forward_byte_count": vector[3],
        "backward_byte_count": vector[4],
        "packet_rate": vector[5],
        "byte_rate": vector[6],
        "is_one_way_flow": vector[7],
    }
    assert payload["ml_detection"] == {
        "model": "guardianx_isolation_forest_v2",
        "schema_version": "v2",
        "prediction": 1,
        "anomaly_score": 0.018434047010596033,
        "features": expected_features,
    }
    assert set(payload["ml_detection"]["features"]) == {
        "flow_duration",
        "forward_packet_count",
        "backward_packet_count",
        "forward_byte_count",
        "backward_byte_count",
        "packet_rate",
        "byte_rate",
        "is_one_way_flow",
    }


def test_transport_reuses_inference_instance_for_multiple_publish_calls() -> None:
    record = completed_flow()
    response = httpx.Response(
        status_code=201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", transport().events_url),
    )

    inference = type(
        "StubInference",
        (),
        {"predict": lambda self, vector: type("Result", (), {"prediction": 1, "anomaly_score": 0.1})()},
    )()

    client = SecurityEventTransport(
        base_url="http://localhost:8000/",
        agent_id=AGENT_ID,
        access_token=ACCESS_TOKEN,
        inference=inference,
    )

    with patch("app.agent.transport.events.httpx.post", return_value=response):
        client.publish(record)
        client.publish(record)

    assert hasattr(client, "inference")


def test_invalid_feature_data_is_handled_explicitly_without_fabricating_ml_output() -> None:
    record = completed_flow()
    response = httpx.Response(
        status_code=201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", transport().events_url),
    )

    inference = type(
        "StubInference",
        (),
        {"predict": lambda self, vector: (_ for _ in ()).throw(ValueError("invalid feature data"))},
    )()

    with patch("app.agent.transport.events.httpx.post", return_value=response) as mock_post:
        SecurityEventTransport(
            base_url="http://localhost:8000/",
            agent_id=AGENT_ID,
            access_token=ACCESS_TOKEN,
            inference=inference,
        ).publish(record)

    payload = mock_post.call_args.kwargs["json"]["payload"]
    assert "ml_detection" not in payload
    assert "features" not in payload


def test_http_error_is_wrapped_as_event_transport_error() -> None:
    record = completed_flow()

    response = httpx.Response(
        status_code=500,
        request=httpx.Request("POST", transport().events_url),
    )

    with patch("app.agent.transport.events.httpx.post", return_value=response):
        with pytest.raises(EventTransportError, match="Failed to publish security event"):
            transport().publish(record)


def test_timeout_is_wrapped_as_event_transport_error() -> None:
    record = completed_flow()

    with patch(
        "app.agent.transport.events.httpx.post",
        side_effect=httpx.TimeoutException("request timed out"),
    ):
        with pytest.raises(EventTransportError, match="Failed to publish security event"):
            transport().publish(record)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "base_url": "",
                "agent_id": AGENT_ID,
                "access_token": ACCESS_TOKEN,
            },
            "base_url cannot be empty",
        ),
        (
            {
                "base_url": "http://localhost:8000",
                "agent_id": AGENT_ID,
                "access_token": "",
            },
            "access_token cannot be empty",
        ),
        (
            {
                "base_url": "http://localhost:8000",
                "agent_id": AGENT_ID,
                "access_token": ACCESS_TOKEN,
                "timeout": 0,
            },
            "timeout must be positive",
        ),
    ],
)
def test_invalid_configuration_is_rejected(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        SecurityEventTransport(**kwargs)  # type: ignore[arg-type]