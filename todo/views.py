from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.core.paginator import Paginator

from .models import Todo
from .serializers import TodoSerializer


# below class based api view is to create todo
class TodoCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TodoSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "Todo created successfully"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# below class based api view is to get the the list of todo's of logged in user
class TodoListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Base queryset (always user-scoped)
        todos = Todo.objects.filter(user=request.user)

        # 2. Search by title
        search = request.query_params.get("search")
        if search:
            todos = todos.filter(title__icontains=search)

        # 3. Filter by completion status
        is_completed = request.query_params.get("is_completed")
        if is_completed is not None:
            todos = todos.filter(is_completed=is_completed.lower() == "true")

        # 4. Filter by archive status
        is_archived = request.query_params.get("is_archived")

        if is_archived is not None:
            todos = todos.filter(
                is_archived=is_archived.lower() == "true"
            )

        # 5️ Tag filter (single tag only)
        tag_id = request.query_params.get("tag_id")
        if tag_id:
            todos = todos.filter(tag__tag_code=tag_id)

        # 6️ Due date filter
        due_date = request.query_params.get("due_date")
        if due_date:
            todos = todos.filter(due_date=due_date)

        # 7 Sorting (int-based enum) i.e latest (1) or oldest (2)
        sort_order = request.query_params.get("sort_order")

        if sort_order == "2":
            # Oldest first
            todos = todos.order_by("created_at")
        else:
            # Default & sort_order=1 → Latest first
            todos = todos.order_by("-created_at")

        # 8 Pagination
        page_number = request.query_params.get("page", 1)
        paginator = Paginator(todos, 12)  # 9 todos per page
        page = paginator.get_page(page_number)

        serializer = TodoSerializer(page, many=True)

        return Response({
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page.number,
            "results": serializer.data
        })


# below class based api view is to update the todo of logged in user
class TodoUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        todo_id = request.data.get("todo_id")

        if not todo_id:
            return Response(
                {"error": "todo_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            todo = Todo.objects.get(id=todo_id, user=request.user)
        except Todo.DoesNotExist:
            return Response(
                {"error": "Todo not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Remove todo_id from payload before serializer
        update_data = request.data.copy()
        update_data.pop("todo_id", None)

        serializer = TodoSerializer(
            todo,
            data=update_data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Todo updated successfully"},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# below class based api view is to delete the todo of logged in user
class TodoDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        todo_id = request.query_params.get("todo_id")

        if not todo_id:
            return Response(
                {"error": "todo_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            todo = Todo.objects.get(id=todo_id, user=request.user)
        except Todo.DoesNotExist:
            return Response(
                {"error": "Todo not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        todo.delete() #delete that row whose id gets matched to the todo_id

        return Response(
            {"message": "Todo deleted successfully"},
            status=status.HTTP_200_OK
        )