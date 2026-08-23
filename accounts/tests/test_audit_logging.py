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
def test_login_success_emits_safe_audit_metadata(client, user_factory, caplog):
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
    client, user_factory, caplog
):
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
def test_throttle_blocked_login_emits_a_safe_audit_record(client, user_factory, caplog):
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
    assert "Invalid username or password." in blocked_response.content.decode()
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
        "managed_account_updated actor='portal-admin' target='renamed-crew'",
        "managed_account_deactivated actor='portal-admin' target='renamed-crew'",
        "managed_account_reactivated actor='portal-admin' target='renamed-crew'",
        "managed_account_password_reset actor='portal-admin' target='renamed-crew'",
    ]
    audit_output = "\n".join(messages)
    assert creation_password not in audit_output
    assert reset_password not in audit_output
