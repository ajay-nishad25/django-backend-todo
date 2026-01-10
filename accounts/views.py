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