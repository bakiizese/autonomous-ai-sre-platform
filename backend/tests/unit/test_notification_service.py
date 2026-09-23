from unittest.mock import patch

import pytest

from app.db.models import EmailSubscriber, Issue, IssueOrigin, RemediationRun, Repo, RepoType, RunStatus, RunTriggerSource
from app.services import notification_service


def _make_run(db_session, risk_score, repo_type=RepoType.sandbox, repo_full_name="octocat/notif-test"):
    repo = Repo(owner="octocat", name="notif-test", full_name=repo_full_name, repo_type=repo_type)
    db_session.add(repo)
    db_session.flush()
    issue = Issue(repo_id=repo.id, issue_number=7, title="Boom", origin=IssueOrigin.poller_detected)
    db_session.add(issue)
    db_session.flush()
    run = RemediationRun(
        issue_id=issue.id,
        repo_id=repo.id,
        trigger_source=RunTriggerSource.poller,
        status=RunStatus.awaiting_approval,
        risk_score=risk_score,
        diagnosis_summary="Something broke",
        root_cause_analysis="A None crept in.",
    )
    db_session.add(run)
    db_session.commit()
    return repo, issue, run


@pytest.mark.parametrize("threshold,risk_score", [(8, 8), (8, 5), (8, None)])
def test_notify_subscribers_skips_when_at_or_below_threshold_or_unset(db_session, threshold, risk_score):
    repo, issue, run = _make_run(db_session, risk_score=risk_score)
    db_session.add(EmailSubscriber(repo_id=repo.id, email="watcher@example.com", unsubscribe_token="tok1"))
    db_session.commit()

    with patch("app.services.notification_service.settings") as mock_settings, patch.object(
        notification_service, "send_critical_alert"
    ) as mock_send:
        mock_settings.CRITICAL_RISK_THRESHOLD = threshold
        notification_service.notify_subscribers(db_session, run)
        mock_send.assert_not_called()


def test_notify_subscribers_sends_to_repo_and_global_subscribers(db_session):
    repo, issue, run = _make_run(db_session, risk_score=9)
    db_session.add(EmailSubscriber(repo_id=repo.id, email="repo-watcher@example.com", unsubscribe_token="tok2"))
    db_session.add(EmailSubscriber(repo_id=None, email="admin@example.com", unsubscribe_token="tok3", is_admin_fallback=True))
    db_session.commit()

    with patch("app.services.notification_service.settings") as mock_settings, patch.object(
        notification_service, "send_critical_alert"
    ) as mock_send:
        mock_settings.CRITICAL_RISK_THRESHOLD = 8
        notification_service.notify_subscribers(db_session, run)

        assert mock_send.call_count == 2
        recipients = {call.args[0] for call in mock_send.call_args_list}
        assert recipients == {"repo-watcher@example.com", "admin@example.com"}
        # pr_url should be None since approval hasn't happened yet
        assert all(call.args[5] is None for call in mock_send.call_args_list)


def test_notify_subscribers_skips_unsubscribed(db_session):
    repo, issue, run = _make_run(db_session, risk_score=9)
    from datetime import datetime, timezone

    db_session.add(
        EmailSubscriber(
            repo_id=repo.id,
            email="left@example.com",
            unsubscribe_token="tok4",
            unsubscribed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    with patch("app.services.notification_service.settings") as mock_settings, patch.object(
        notification_service, "send_critical_alert"
    ) as mock_send:
        mock_settings.CRITICAL_RISK_THRESHOLD = 8
        notification_service.notify_subscribers(db_session, run)
        mock_send.assert_not_called()


def test_notify_subscribers_does_not_cross_repo(db_session):
    repo_a, issue_a, run_a = _make_run(db_session, risk_score=9, repo_full_name="octocat/repo-a")
    repo_b = Repo(owner="octocat", name="repo-b", full_name="octocat/repo-b", repo_type=RepoType.sandbox)
    db_session.add(repo_b)
    db_session.flush()
    db_session.add(EmailSubscriber(repo_id=repo_b.id, email="other-repo-watcher@example.com", unsubscribe_token="tok5"))
    db_session.commit()

    with patch("app.services.notification_service.settings") as mock_settings, patch.object(
        notification_service, "send_critical_alert"
    ) as mock_send:
        mock_settings.CRITICAL_RISK_THRESHOLD = 8
        notification_service.notify_subscribers(db_session, run_a)
        mock_send.assert_not_called()


def test_seed_admin_subscriber_creates_once(db_session):
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.ADMIN_ALERT_EMAIL = "owner@example.com"
        notification_service.seed_admin_subscriber(db_session)
        notification_service.seed_admin_subscriber(db_session)

        rows = db_session.query(EmailSubscriber).filter_by(email="owner@example.com", is_admin_fallback=True).all()
        assert len(rows) == 1
        assert rows[0].repo_id is None


def test_seed_admin_subscriber_noop_when_unset(db_session):
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.ADMIN_ALERT_EMAIL = ""
        notification_service.seed_admin_subscriber(db_session)

        assert db_session.query(EmailSubscriber).count() == 0


def test_subscribe_then_unsubscribe_roundtrip(db_session):
    sub = notification_service.subscribe(db_session, "visitor@example.com", repo_id=None)
    assert sub.unsubscribed_at is None

    ok = notification_service.unsubscribe(db_session, sub.unsubscribe_token)
    assert ok is True

    refreshed = db_session.get(EmailSubscriber, sub.id)
    assert refreshed.unsubscribed_at is not None


def test_subscribe_is_idempotent_and_reactivates(db_session):
    first = notification_service.subscribe(db_session, "repeat@example.com", repo_id=None)
    notification_service.unsubscribe(db_session, first.unsubscribe_token)

    second = notification_service.subscribe(db_session, "repeat@example.com", repo_id=None)

    assert second.id == first.id
    assert second.unsubscribed_at is None


def test_unsubscribe_unknown_token_returns_false(db_session):
    assert notification_service.unsubscribe(db_session, "does-not-exist") is False
