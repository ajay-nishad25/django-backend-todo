from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

from accounts.views import SignupView, LoginView, LogoutView, ResetPasswordView, UpdateThemeView
from todo.views import (
    TodoCreateView,
    TodoListView,
    TodoUpdateView,
    TodoDeleteView,
    
)

# Health-check: intentionally plain Django view (no DRF, no auth, no DB)
def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [

    path('admin/', admin.site.urls),

    # Public health-check (no auth, no DB) — used by cron-job.org to keep Render warm
    path('health/', health_check, name='health-check'),

    # AUTH APIs (Company-style token auth)
    path('api/signup/', SignupView.as_view(), name='signup'),
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/logout/', LogoutView.as_view(), name='logout'),
    path("api/reset-password/", ResetPasswordView.as_view(), name="reset-password"),
    path("api/update-theme/", UpdateThemeView.as_view(), name="update-theme"),


    # Todo APIs
    path('api/create-todo/', TodoCreateView.as_view(), name='create-todo'),
    path('api/get-todos/', TodoListView.as_view(), name='get-todos'),
    path('api/update-todo/', TodoUpdateView.as_view(), name='update-todo'),
    path('api/delete-todo/', TodoDeleteView.as_view(), name='delete-todo')

]
