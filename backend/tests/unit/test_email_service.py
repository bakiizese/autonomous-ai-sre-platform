from unittest.mock import MagicMock, patch
import pytest

# Import from email_service
from app.services.email_service import send_critical_alert


@pytest.fixture
def mock_smtp_settings():
    """Provides a fully populated settings object for SMTP testing."""
    # Updated path to patch settings inside app.services.email_service
    with patch("app.services.email_service.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "alerts@example.com"
        mock_settings.SMTP_PASSWORD = "secret-password"
        mock_settings.ALERT_EMAIL_FROM = "sentinel@example.com"
        mock_settings.ALERT_EMAIL_TO = "sre-team@example.com"
        yield mock_settings


@pytest.fixture
def sample_alert_data():
    """Provides standard inputs for the email alert function."""
    return {
        "issue_number": 101,
        "issue_title": "Database Connection Leak",
        "risk_score": 9,
        "root_cause": "Unclosed connections in connection pool under high load.",
        "pr_url": "https://github.com/org/repo/pull/42",
    }


@patch("smtplib.SMTP")
def test_send_critical_alert_success(
    mock_smtp_cls, mock_smtp_settings, sample_alert_data
):
    """Test successful email creation and transmission over SMTP with TLS."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    send_critical_alert(**sample_alert_data)

    mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("alerts@example.com", "secret-password")

    mock_server.sendmail.assert_called_once()
    from_addr, to_addrs, raw_msg = mock_server.sendmail.call_args[0]

    assert from_addr == "sentinel@example.com"
    assert to_addrs == ["sre-team@example.com"]
    assert "Subject: [Sentinel SRE] Critical issue #101 (risk 9/10)" in raw_msg
    assert "Issue: #101 - Database Connection Leak" in raw_msg
    assert "Pull request: https://github.com/org/repo/pull/42" in raw_msg


@patch("smtplib.SMTP")
def test_send_critical_alert_fallback_from_address(
    mock_smtp_cls, mock_smtp_settings, sample_alert_data
):
    """Test falling back to SMTP_USER when ALERT_EMAIL_FROM is not set."""
    mock_smtp_settings.ALERT_EMAIL_FROM = None
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    send_critical_alert(**sample_alert_data)

    from_addr = mock_server.sendmail.call_args[0][0]
    assert from_addr == "alerts@example.com"


@patch("smtplib.SMTP")
def test_send_critical_alert_without_pr_url(
    mock_smtp_cls, mock_smtp_settings, sample_alert_data
):
    """Test message formatting when no PR URL is provided."""
    sample_alert_data["pr_url"] = None
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    send_critical_alert(**sample_alert_data)

    raw_msg = mock_server.sendmail.call_args[0][2]
    assert (
        "No pull request was opened (sandbox verification may have failed)." in raw_msg
    )


@pytest.mark.parametrize(
    "host,to_email",
    [
        (None, "sre@example.com"),
        ("smtp.example.com", None),
        (None, None),
    ],
)
@patch("smtplib.SMTP")
@patch("app.services.email_service.logger")
def test_send_critical_alert_skipped_when_unconfigured(
    mock_logger, mock_smtp_cls, mock_smtp_settings, sample_alert_data, host, to_email
):
    """Test that email sending is safely skipped when SMTP_HOST or ALERT_EMAIL_TO is missing."""
    mock_smtp_settings.SMTP_HOST = host
    mock_smtp_settings.ALERT_EMAIL_TO = to_email

    send_critical_alert(**sample_alert_data)

    mock_smtp_cls.assert_not_called()
    mock_logger.warning.assert_called_once_with(
        "Email alert skipped: SMTP_HOST or ALERT_EMAIL_TO not configured."
    )


@patch("smtplib.SMTP")
@patch("app.services.email_service.logger")
def test_send_critical_alert_smtp_exception_handled(
    mock_logger, mock_smtp_cls, mock_smtp_settings, sample_alert_data
):
    """Test exception handling and logging when SMTP server fails or times out."""
    mock_smtp_cls.side_effect = Exception("Connection timed out")

    send_critical_alert(**sample_alert_data)

    mock_logger.error.assert_called_once()
    assert (
        "Failed to send critical alert email: Connection timed out"
        in mock_logger.error.call_args[0][0]
    )
