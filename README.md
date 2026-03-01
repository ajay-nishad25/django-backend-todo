# Learning backend with django

## Django Backend — Todo Fullstack Project

A Django REST API backend for the Todo application. This guide walks you through setting up the development environment from scratch.

## Required Frontend Repository

[react-frontend-todo](https://github.com/ajay-nishad25/react-frontend-todo)

---

## Getting Started

### Prerequisites

- Python 3.x installed
- pip package manager

---

### Step 1 — Clone the Repository

Clone the repository and navigate to the root directory where `manage.py` resides.

---

### Step 2 — Create a Virtual Environment

Run the following command at the root level to create a virtual environment:
```bash
python -m venv venv
```

Then activate it:
```bash
venv\Scripts\Activate
```

Once activated, your terminal prompt should look like this:
```
(venv) PS C:\Users\...\
```

---

### Step 3 — Install Dependencies

With the virtual environment active, install all required dependencies:
```bash
pip install -r requirements.txt
```

---

### Step 4 — Verify Django Installation

Confirm that Django was installed successfully:
```bash
python -m django --version
```

Expected output:
```
5.2 or greater
```

---

### Step 5 — Run Migrations
```bash
python manage.py migrate
```

---

### Step 6 — Create a Superuser
```bash
python manage.py createsuperuser
```

After creating the superuser, if you attempt to run the server without a `.env` file, you may encounter the following error:
```
CommandError: You must set settings.ALLOWED_HOSTS if DEBUG is False.
```

Proceed to the next step to resolve this.

---

### Step 7 — Configure Environment Variables

Create a `.env` file at the root level (same directory as `manage.py`) and add the following:
```env
SECRET_KEY=<YOUR_SECRET_KEY_HERE>
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

---

### Step 8 — Generate a Secret Key

To generate a secure `SECRET_KEY`, open the Django shell:
```bash
python manage.py shell
```

Then run:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Copy the output and replace `<YOUR_SECRET_KEY_HERE>` in your `.env` file with it.

---

### Step 9 — Start the Development Server
```bash
python manage.py runserver
```

Once the server is running, open your browser and navigate to:
```
http://127.0.0.1:8000/admin/
```

---

### Step 10 — Log In as Superuser

Use the superuser credentials you created in **Step 6** to log in to the Django admin panel.

---

### Step 11 — Create Tags

In the admin panel, navigate to the **Tags** section and create the following tags:

| # | Tag Name |
|---|----------|
| 1 | Urgent |
| 2 | Highest Priority |
| 3 | Mid Priority |
| 4 | Low Priority |
| 5 | Someday / Maybe |

---

### Step 12 — Connect the Frontend

Your backend is now fully set up. Head over to the [frontend repository](https://github.com/ajay-nishad25/react-frontend-todo) and log in using the superuser credentials.



check grammar and put in professional guide for running this backend project note this should be in markdown language so that i can put this to my github .md file
