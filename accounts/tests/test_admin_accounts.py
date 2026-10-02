import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from accounts.models import manageable_users
from accounts.services import (
    AccountRuleViolation,
    create_managed_user,
    reset_temporary_password,
    set_user_active,
    update_managed_user,
)

ADMIN_ROUTES = [
    ("accounts:admin_user_list", {}),
    ("accounts:admin_user_create", {}),
    ("accounts:admin_user_edit", {"pk": 1}),
    ("accounts:admin_user_deactivate", {"pk": 1}),
    ("accounts:admin_user_reactivate", {"pk": 1}),
    ("accounts:admin_user_reset_password", {"pk": 1}),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name, kwargs",
    ADMIN_ROUTES,
)
def test_normal_user_gets_forbidden_from_every_portal_admin_route(
    client, user_factory, route_name, kwargs
):
    client.force_login(user_factory())

    response = client.get(reverse(route_name, kwargs=kwargs))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name, kwargs",
    ADMIN_ROUTES,
)
def test_anonymous_visitor_is_redirected_to_login_from_every_portal_admin_route(
    client, route_name, kwargs
):
    # Anonymous visitors are redirected to login, like on every other
    # authenticated route -- only a logged-in non-admin gets a 403.
    url = reverse(route_name, kwargs=kwargs)

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"/account/login/?next={url}"


@pytest.mark.django_db
def test_portal_admin_can_create_managed_user(client, portal_admin):
    client.force_login(portal_admin)

    response = client.post(
        reverse("accounts:admin_user_create"),
        {"username": "new-crew", "temporary_password": "Temp-Only-42!"},
    )

    assert response.status_code == 302
    created = portal_admin.__class__.objects.get(username="new-crew")
    assert created.must_change_password is True
    assert created.check_password("Temp-Only-42!")
    assert created.is_portal_admin is False
    assert created.is_staff is False
    assert created.is_superuser is False


@pytest.mark.django_db
def test_account_creation_ignores_superuser_from_request_data(client, portal_admin):
    client.force_login(portal_admin)

    response = client.post(
        reverse("accounts:admin_user_create"),
        {
            "username": "ordinary-crew",
            "temporary_password": "Temp-Only-42!",
            "is_superuser": "on",
        },
    )

    assert response.status_code == 302
    assert portal_admin.__class__.objects.get(username="ordinary-crew").is_superuser is False


@pytest.mark.django_db
def test_portal_admin_can_deactivate_reactivate_and_reset_account(portal_admin, user_factory):
    crew_member = user_factory(username="crew-member")

    set_user_active(actor=portal_admin, user=crew_member, active=False)
    crew_member.refresh_from_db()
    assert crew_member.is_active is False

    set_user_active(actor=portal_admin, user=crew_member, active=True)
    reset_temporary_password(
        actor=portal_admin,
        user=crew_member,
        temporary_password="Replacement-Password-42!",
    )
    crew_member.refresh_from_db()
    assert crew_member.is_active is True
    assert crew_member.must_change_password is True
    assert crew_member.check_password("Replacement-Password-42!")


@pytest.mark.django_db
def test_non_admin_cannot_mutate_managed_accounts(user_factory):
    actor = user_factory(username="ordinary-user")

    with pytest.raises(PermissionDenied):
        create_managed_user(
            actor=actor,
            username="new-crew",
            temporary_password="Temp-Only-42!",
        )


@pytest.mark.django_db
def test_portal_admin_cannot_mutate_staff_or_superuser_accounts(portal_admin, user_factory):
    protected_user = user_factory(username="django-admin", is_staff=True, is_superuser=True)

    with pytest.raises(PermissionDenied):
        set_user_active(actor=portal_admin, user=protected_user, active=False)
    with pytest.raises(PermissionDenied):
        reset_temporary_password(
            actor=portal_admin,
            user=protected_user,
            temporary_password="Replacement-Password-42!",
        )
    with pytest.raises(PermissionDenied):
        update_managed_user(
            actor=portal_admin,
            user=protected_user,
            username="taken-over-admin",
            active=True,
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name, payload",
    [
        ("accounts:admin_user_edit", {"username": "renamed", "is_active": "on"}),
        ("accounts:admin_user_deactivate", {}),
        ("accounts:admin_user_reactivate", {}),
        ("accounts:admin_user_reset_password", {"temporary_password": "Replacement-Password-42!"}),
    ],
)
def test_normal_user_cannot_mutate_accounts_with_post(
    client, user_factory, route_name, payload
):
    normal_user = user_factory(username="ordinary-user")
    target = user_factory(username="crew-member")
    original_password = target.password
    client.force_login(normal_user)

    response = client.post(reverse(route_name, kwargs={"pk": target.pk}), payload)

    target.refresh_from_db()
    assert response.status_code == 403
    assert target.username == "crew-member"
    assert target.is_active is True
    assert target.password == original_password


@pytest.mark.django_db
def test_account_list_exposes_all_management_actions_with_csrf(client, portal_admin, user_factory):
    crew_member = user_factory(username="crew-member")
    client.force_login(portal_admin)

    response = client.get(reverse("accounts:admin_user_list"))

    content = response.content.decode()
    assert reverse("accounts:admin_user_edit", kwargs={"pk": crew_member.pk}) in content
    assert reverse("accounts:admin_user_deactivate", kwargs={"pk": crew_member.pk}) in content
    assert reverse("accounts:admin_user_reset_password", kwargs={"pk": crew_member.pk}) in content
    assert 'method="post"' in content
    assert 'name="csrfmiddlewaretoken"' in content

    crew_member.is_active = False
    crew_member.save(update_fields=["is_active"])
    inactive_content = client.get(reverse("accounts:admin_user_list")).content.decode()
    assert reverse("accounts:admin_user_reactivate", kwargs={"pk": crew_member.pk}) in inactive_content


@pytest.mark.django_db
def test_portal_admin_can_complete_management_flows_over_http(client, portal_admin, user_factory):
    crew_member = user_factory(username="crew-member")
    client.force_login(portal_admin)

    edit = client.post(
        reverse("accounts:admin_user_edit", kwargs={"pk": crew_member.pk}),
        {"username": "renamed-crew", "is_active": "on"},
    )
    deactivate = client.post(
        reverse("accounts:admin_user_deactivate", kwargs={"pk": crew_member.pk})
    )
    crew_member.refresh_from_db()
    reactivate = client.post(
        reverse("accounts:admin_user_reactivate", kwargs={"pk": crew_member.pk})
    )
    reset = client.post(
        reverse("accounts:admin_user_reset_password", kwargs={"pk": crew_member.pk}),
        {"temporary_password": "Replacement-Password-42!"},
    )

    crew_member.refresh_from_db()
    assert edit.status_code == 302
    assert deactivate.status_code == 302
    assert reactivate.status_code == 302
    assert reset.status_code == 302
    assert crew_member.username == "renamed-crew"
    assert crew_member.is_active is True
    assert crew_member.must_change_password is True
    assert crew_member.check_password("Replacement-Password-42!")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "staff_flags",
    [{"is_staff": True}, {"is_superuser": True}, {"is_staff": True, "is_superuser": True}],
)
def test_portal_admin_routes_treat_staff_and_superusers_as_missing(
    client, portal_admin, user_factory, staff_flags
):
    protected = user_factory(username="django-admin", **staff_flags)
    original_password = protected.password
    client.force_login(portal_admin)

    listing = client.get(reverse("accounts:admin_user_list")).content.decode()
    responses = [
        client.get(reverse("accounts:admin_user_edit", kwargs={"pk": protected.pk})),
        client.get(reverse("accounts:admin_user_reset_password", kwargs={"pk": protected.pk})),
        client.post(
            reverse("accounts:admin_user_edit", kwargs={"pk": protected.pk}),
            {"username": "taken-over-admin", "is_active": "on"},
        ),
        client.post(reverse("accounts:admin_user_deactivate", kwargs={"pk": protected.pk})),
        client.post(reverse("accounts:admin_user_reactivate", kwargs={"pk": protected.pk})),
        client.post(
            reverse("accounts:admin_user_reset_password", kwargs={"pk": protected.pk}),
            {"temporary_password": "Replacement-Password-42!"},
        ),
    ]

    protected.refresh_from_db()
    assert "django-admin" not in listing
    assert [response.status_code for response in responses] == [404] * 6
    assert protected.username == "django-admin"
    assert protected.is_active is True
    assert protected.password == original_password


@pytest.mark.django_db
def test_account_list_shows_managed_accounts_sorted_by_username(
    client, portal_admin, user_factory
):
    user_factory(username="zulu-crew")
    user_factory(username="alpha-crew")
    client.force_login(portal_admin)

    response = client.get(reverse("accounts:admin_user_list"))

    assert [user.username for user in response.context["users"]] == [
        "alpha-crew",
        "portal-admin",
        "zulu-crew",
    ]


@pytest.mark.django_db
def test_portal_admin_cannot_reset_their_own_password_through_the_admin_views(
    client, portal_admin
):
    client.force_login(portal_admin)
    old_hash = portal_admin.password

    reset = client.post(
        reverse("accounts:admin_user_reset_password", kwargs={"pk": portal_admin.pk}),
        {"temporary_password": "Replacement-Password-42!"},
    )

    portal_admin.refresh_from_db()
    assert reset.status_code == 200
    assert "Dein eigenes Passwort kannst du hier nicht zurücksetzen." in reset.content.decode()
    assert portal_admin.password == old_hash
    assert portal_admin.must_change_password is False


@pytest.mark.django_db
def test_portal_admin_cannot_deactivate_their_own_account(client, portal_admin, user_factory):
    user_factory(username="second-admin", is_portal_admin=True)
    client.force_login(portal_admin)

    response = client.post(
        reverse("accounts:admin_user_deactivate", kwargs={"pk": portal_admin.pk}),
        follow=True,
    )

    portal_admin.refresh_from_db()
    assert response.redirect_chain == [(reverse("accounts:admin_user_list"), 302)]
    assert portal_admin.is_active is True
    assert "Du kannst dein eigenes Konto nicht deaktivieren." in response.content.decode()


@pytest.mark.django_db
def test_unticking_aktiv_in_the_own_edit_form_is_refused(client, portal_admin, user_factory):
    user_factory(username="second-admin", is_portal_admin=True)
    client.force_login(portal_admin)

    response = client.post(
        reverse("accounts:admin_user_edit", kwargs={"pk": portal_admin.pk}),
        {"username": portal_admin.username},
    )

    portal_admin.refresh_from_db()
    assert response.status_code == 200
    assert "Du kannst dein eigenes Konto nicht deaktivieren." in response.content.decode()
    assert portal_admin.is_active is True


@pytest.mark.django_db
def test_the_last_active_portal_admin_cannot_be_deactivated(user_factory, portal_admin):
    # The actor's request raced with their own deactivation: the object is a
    # portal admin but no longer active, so ``portal_admin`` is the last one.
    stale_actor = user_factory(username="stale-admin", is_portal_admin=True, is_active=False)

    with pytest.raises(AccountRuleViolation, match="letzte aktive Portal-Administrator"):
        set_user_active(actor=stale_actor, user=portal_admin, active=False)

    portal_admin.refresh_from_db()
    assert portal_admin.is_active is True


@pytest.mark.django_db
def test_a_colleague_admin_stays_manageable(client, portal_admin, user_factory):
    colleague = user_factory(username="colleague", is_portal_admin=True)
    client.force_login(portal_admin)

    reset = client.post(
        reverse("accounts:admin_user_reset_password", kwargs={"pk": colleague.pk}),
        {"temporary_password": "Replacement-Password-42!"},
    )
    deactivate = client.post(
        reverse("accounts:admin_user_deactivate", kwargs={"pk": colleague.pk})
    )

    colleague.refresh_from_db()
    assert reset.status_code == 302 and deactivate.status_code == 302
    assert colleague.must_change_password is True
    assert colleague.is_active is False


@pytest.mark.django_db
def test_denied_account_attempts_are_audited(client, portal_admin, user_factory, caplog):
    user_factory(username="second-admin", is_portal_admin=True)
    player = user_factory(username="player")
    client.force_login(portal_admin)

    with caplog.at_level("INFO", logger="accounts.audit"):
        client.post(reverse("accounts:admin_user_deactivate", kwargs={"pk": portal_admin.pk}))
        client.force_login(player)
        denied = client.get(reverse("accounts:admin_user_list"))

    assert denied.status_code == 403
    messages = [r.getMessage() for r in caplog.records if r.name == "accounts.audit"]
    assert (
        "managed_account_denied actor='portal-admin' action=deactivate-self target='portal-admin'"
        in messages
    )
    assert any(
        m.startswith("admin_access_denied username='player' method=GET path='/portal-admin/accounts/")
        for m in messages
    )


@pytest.mark.django_db
def test_invalid_account_forms_rerender_with_errors(client, portal_admin, user_factory):
    crew_member = user_factory(username="crew-member")
    client.force_login(portal_admin)

    create = client.post(
        reverse("accounts:admin_user_create"),
        {"username": "crew-member", "temporary_password": "Temp-Only-42!"},
    )
    edit = client.post(
        reverse("accounts:admin_user_edit", kwargs={"pk": crew_member.pk}),
        {"username": "portal-admin", "is_active": "on"},
    )
    reset = client.post(
        reverse("accounts:admin_user_reset_password", kwargs={"pk": crew_member.pk}),
        {"temporary_password": "short"},
    )

    crew_member.refresh_from_db()
    for response in (create, edit, reset):
        assert response.status_code == 200
        assert response.templates[0].name == "accounts/user_form.html"
    assert create.context["form"].errors == {
        "username": ["Dieser Benutzername ist bereits vergeben."]
    }
    assert list(edit.context["form"].errors) == ["username"]
    assert list(reset.context["form"].errors) == ["temporary_password"]
    assert crew_member.username == "crew-member"
    assert crew_member.must_change_password is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name",
    ["accounts:admin_user_create", "accounts:admin_user_edit", "accounts:admin_user_reset_password"],
)
def test_account_form_pages_render_an_unbound_form(client, portal_admin, user_factory, route_name):
    crew_member = user_factory(username="crew-member")
    client.force_login(portal_admin)
    kwargs = {} if route_name == "accounts:admin_user_create" else {"pk": crew_member.pk}

    response = client.get(reverse(route_name, kwargs=kwargs))

    assert response.status_code == 200
    assert response.templates[0].name == "accounts/user_form.html"
    assert response.context["form"].is_bound is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route_name", ["accounts:admin_user_deactivate", "accounts:admin_user_reactivate"]
)
def test_account_actions_reject_get(client, portal_admin, user_factory, route_name):
    crew_member = user_factory(username="crew-member")
    client.force_login(portal_admin)

    response = client.get(reverse(route_name, kwargs={"pk": crew_member.pk}))

    crew_member.refresh_from_db()
    assert response.status_code == 405
    assert crew_member.is_active is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "flags, manageable",
    [
        ({}, True),
        ({"is_portal_admin": True}, True),
        ({"is_staff": True}, False),
        ({"is_superuser": True}, False),
        ({"is_staff": True, "is_superuser": True}, False),
    ],
)
def test_manageable_property_and_queryset_agree(user_factory, flags, manageable):
    user = user_factory(**flags)

    assert user.is_manageable is manageable
    assert manageable_users().filter(pk=user.pk).exists() is manageable


@pytest.mark.django_db
def test_account_forms_are_german(client, portal_admin, user_factory):
    crew_member = user_factory(username="crew-member")
    client.force_login(portal_admin)

    create = client.get(reverse("accounts:admin_user_create")).content.decode()
    edit = client.get(
        reverse("accounts:admin_user_edit", kwargs={"pk": crew_member.pk})
    ).content.decode()
    reset = client.get(
        reverse("accounts:admin_user_reset_password", kwargs={"pk": crew_member.pk})
    ).content.decode()

    assert "Benutzername" in create and "Tempor&auml;res Passwort" in create.replace("ä", "&auml;")
    assert "Benutzername" in edit and "Aktiv" in edit
    assert "Tempor&auml;res Passwort" in reset.replace("ä", "&auml;")
    for page in (create, edit, reset):
        assert "Username" not in page and "Password" not in page and "Active" not in page

    blank = client.post(reverse("accounts:admin_user_create"), {})
    # Django's own messages follow LANGUAGE_CODE.
    assert blank.context["form"].errors["username"] == ["Dieses Feld ist zwingend erforderlich."]

