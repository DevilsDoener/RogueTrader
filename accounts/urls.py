from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("account/login/", views.login_view, name="login"),
    path("account/logout/", views.logout_view, name="logout"),
    path("account/change-required/", views.change_required, name="change_required"),
    path("portal-admin/accounts/", views.PortalAdminUserListView.as_view(), name="admin_user_list"),
    path("portal-admin/accounts/create/", views.PortalAdminUserCreateView.as_view(), name="admin_user_create"),
    path("portal-admin/accounts/<int:pk>/edit/", views.PortalAdminUserUpdateView.as_view(), name="admin_user_edit"),
    path("portal-admin/accounts/<int:pk>/deactivate/", views.PortalAdminUserActionView.as_view(action="deactivate"), name="admin_user_deactivate"),
    path("portal-admin/accounts/<int:pk>/reactivate/", views.PortalAdminUserActionView.as_view(action="reactivate"), name="admin_user_reactivate"),
    path("portal-admin/accounts/<int:pk>/reset-password/", views.PortalAdminPasswordResetView.as_view(), name="admin_user_reset_password"),
]
