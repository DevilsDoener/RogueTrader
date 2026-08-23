import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user_factory(db):
    def create_user(**attributes):
        password = attributes.pop("password", "Valid-Password-42!")
        attributes.setdefault("must_change_password", False)
        username = attributes.pop("username", "user")
        user = get_user_model().objects.create_user(
            username=username,
            password=password,
            **attributes,
        )
        return user

    return create_user
