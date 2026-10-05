from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """Primary organizations: Forbmax (manager) and NIMAR (client)."""

    class Code(models.TextChoices):
        FORBMAX = "FORBMAX", "Forbmax"
        NIMAR = "NIMAR", "NIMAR"

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=32, unique=True, choices=Code.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.FORBMAX_ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Authenticated identity with organization + role authorization."""

    class Role(models.TextChoices):
        FORBMAX_ADMIN = "FORBMAX_ADMIN", "Forbmax Admin"
        FORBMAX_MEMBER = "FORBMAX_MEMBER", "Forbmax Member"
        NIMAR_USER = "NIMAR_USER", "NIMAR User"

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["name", "email"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"

    @property
    def is_forbmax(self) -> bool:
        return self.role in {self.Role.FORBMAX_ADMIN, self.Role.FORBMAX_MEMBER}

    @property
    def is_forbmax_admin(self) -> bool:
        return self.role == self.Role.FORBMAX_ADMIN

    @property
    def is_nimar(self) -> bool:
        return self.role == self.Role.NIMAR_USER

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if not self.organization_id:
            return
        code = self.organization.code
        if self.role in {self.Role.FORBMAX_ADMIN, self.Role.FORBMAX_MEMBER} and code != Organization.Code.FORBMAX:
            raise ValidationError("Forbmax roles require the Forbmax organization.")
        if self.role == self.Role.NIMAR_USER and code != Organization.Code.NIMAR:
            raise ValidationError("NIMAR User role requires the NIMAR organization.")
