from django.contrib.auth import get_user_model, authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from .serializers import UserSerializer


User = get_user_model()


# Create new account for user
class SignupView(APIView):
    permission_classes = []  # public

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Validation
        if not email or not password:
            return Response(
                {"error": "Email and password required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "User already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user
        User.objects.create_user(email=email, password=password)

        return Response(
            {"message": "Account created successfully"},
            status=status.HTTP_201_CREATED
        )


# Login user 
class LoginView(APIView):
    permission_classes = []  # public

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        # Validation
        if not email or not password:
            return Response(
                {"error": "Email and password required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        user = authenticate(email=email, password=password)

        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Create or get persistent token
        token, created = Token.objects.get_or_create(user=user)
        user_data = UserSerializer(user).data
        user_name = user.email.split("@")[0]

        return Response(
            {
                "token": token.key,
                "user_data": {
                    **user_data,
                    "user_name": user_name
                }
            },
            status=status.HTTP_200_OK
        )

# Logout user
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delete the token linked to the current user
        request.user.auth_token.delete()

        return Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK
        )


class ResetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        # if any field is empty
        if not current_password or not new_password or not confirm_password:
            return Response(
                {"error": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # check current password
        if not user.check_password(current_password):
            return Response(
                {"error": "Current password is incorrect"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # check new and confirm password 
        if new_password != confirm_password:
            return Response(
                {"error": "New and confirm password do not match"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_password == current_password:
            return Response(
                {"error": "New password cannot be same as current password"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password reset successfully, Please login again"},
            status=status.HTTP_200_OK
        )