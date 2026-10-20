from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Account with a coarse role used for role-based permissions."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        USER = "user", "User"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER, db_index=True)

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser
