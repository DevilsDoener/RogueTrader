import logging

import pytest
from django.urls import reverse

from accounts.services import (
    create_managed_user,
    reset_temporary_password,
    set_user_active,
    update_managed_user,
)


def _audit_messages(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "accounts.audit"
    ]


@pytest.mark.django_db
def test_login_success_emits_safe_audit_metadata(client, user_factory, caplog, settings):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.5"]
    password = "Login-Secret-42!"
    csrf_value = "csrf-value-must-not-be-logged"
    user_factory(username="crew", password=password)

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        response = client.post(
            reverse("accounts:login"),
            {
                "username": "crew",
                "password": password,
                "csrfmiddlewaretoken": csrf_value,
            },
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_REAL_IP="2001:0db8:0000:0000:0000:0000:0000:0001",
        )

    session_identifier = client.session.session_key
    messages = _audit_messages(caplog)
    assert response.status_code == 302
    assert messages == ["login_success username='crew' source_ip=2001:db8::1"]
    assert session_identifier
    audit_output = "\n".join(messages)
    assert password not in audit_output
    assert csrf_value not in audit_output
    assert session_identifier not in audit_output


@pytest.mark.django_db
def test_wrong_and_unknown_logins_emit_failure_audit_records(
    client, user_factory, caplog, settings
):
    settings.TRUSTED_PROXY_IPS = ["127.0.0.1"]
    user_factory(username="crew", password="Correct-Password-42!")

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        wrong_response = client.post(
            reverse("accounts:login"),
            {"username": "crew", "password": "wrong-known-secret"},
            HTTP_X_REAL_IP="192.0.2.20",
        )
        unknown_response = client.post(
            reverse("accounts:login"),
            {"username": "unknown", "password": "wrong-unknown-secret"},
            HTTP_X_REAL_IP="192.0.2.21",
        )

    assert wrong_response.context["form"].non_field_errors() == unknown_response.context[
        "form"
    ].non_field_errors()
    messages = _audit_messages(caplog)
    assert messages == [
        "login_failure username='crew' source_ip=192.0.2.20",
        "login_failure username='unknown' source_ip=192.0.2.21",
    ]
    audit_output = "\n".join(messages)
    assert "wrong-known-secret" not in audit_output
    assert "wrong-unknown-secret" not in audit_output


@pytest.mark.django_db
def test_throttle_blocked_login_emits_a_safe_audit_record(client, user_factory, caplog, settings):
    settings.TRUSTED_PROXY_IPS = ["127.0.0.1"]
    password = "Correct-Password-42!"
    user_factory(username="crew", password=password)
    login_url = reverse("accounts:login")

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        for _ in range(5):
            client.post(
                login_url,
                {"username": "crew", "password": "wrong"},
                HTTP_X_REAL_IP="192.0.2.30",
            )
        blocked_response = client.post(
            login_url,
            {"username": "crew", "password": password},
            HTTP_X_REAL_IP="192.0.2.30",
        )

    messages = _audit_messages(caplog)
    assert blocked_response.status_code == 200
    assert "Benutzername oder Passwort ungültig." in blocked_response.content.decode()
    assert messages[-1] == "login_throttle_blocked username='crew' source_ip=192.0.2.30"
    assert password not in "\n".join(messages)


@pytest.mark.django_db
def test_managed_account_actions_emit_safe_audit_records(portal_admin, caplog):
    creation_password = "Creation-Secret-42!"
    reset_password = "Reset-Secret-43!"

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        managed_user = create_managed_user(
            actor=portal_admin,
            username="new-crew",
            temporary_password=creation_password,
        )
        update_managed_user(
            actor=portal_admin,
            user=managed_user,
            username="renamed-crew",
            active=True,
        )
        set_user_active(actor=portal_admin, user=managed_user, active=False)
        set_user_active(actor=portal_admin, user=managed_user, active=True)
        reset_temporary_password(
            actor=portal_admin,
            user=managed_user,
            temporary_password=reset_password,
        )

    messages = _audit_messages(caplog)
    assert messages == [
        "managed_account_created actor='portal-admin' target='new-crew'",
        "managed_account_updated actor='portal-admin' target='renamed-crew' "
        "old_username='new-crew' new_username='renamed-crew' active=True",
        "managed_account_deactivated actor='portal-admin' target='renamed-crew'",
        "managed_account_reactivated actor='portal-admin' target='renamed-crew'",
        "managed_account_password_reset actor='portal-admin' target='renamed-crew'",
    ]
    audit_output = "\n".join(messages)
    assert creation_password not in audit_output
    assert reset_password not in audit_output


@pytest.mark.django_db
def test_own_password_change_and_logout_are_audited_without_secrets(client, user_factory, caplog):
    old_password = "Old-Secret-Password-42!"
    new_password = "New-Secret-Password-77!"
    user = user_factory(username="crew", password=old_password, must_change_password=True)
    client.force_login(user)

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        client.post(
            reverse("accounts:change_required"),
            {
                "old_password": old_password,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )
        client.post(reverse("accounts:logout"))

    messages = _audit_messages(caplog)
    assert messages == [
        "password_changed username='crew' source_ip=127.0.0.1",
        "logout username='crew' source_ip=127.0.0.1",
    ]
    assert old_password not in "\n".join(messages)
    assert new_password not in "\n".join(messages)


@pytest.mark.django_db
def test_anonymous_logout_is_not_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        client.post(reverse("accounts:logout"))

    assert _audit_messages(caplog) == []


@pytest.mark.django_db
def test_bootstrap_admin_is_audited_without_the_password(caplog):
    from django.core.management import call_command

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        call_command("bootstrap_admin", username="gm", password="Bootstrap-Secret-42!")

    messages = _audit_messages(caplog)
    assert messages == ["bootstrap_admin_created username='gm'"]


def test_audit_file_handler_writes_rotates_and_creates_its_directory_lazily(tmp_path):
    from accounts.auditlog import AuditFileHandler

    log_file = tmp_path / "missing-dir" / "audit.log"
    handler = AuditFileHandler(str(log_file), maxBytes=200, backupCount=2)
    logger = logging.getLogger("accounts.audit.handler-test")
    logger.propagate = False
    logger.addHandler(handler)
    try:
        assert not log_file.parent.exists()  # nothing touched until a record arrives
        for number in range(12):
            logger.warning("login_failure username=%r source_ip=192.0.2.1 n=%d", "crew", number)
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert log_file.exists()
    assert (tmp_path / "missing-dir" / "audit.log.1").exists()
    assert "login_failure" in log_file.read_text(encoding="utf-8")
