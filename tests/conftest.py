import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User


@pytest.fixture
def seeded_data(db):
    call_command("seed_phase1")


@pytest.fixture
def admin_client(seeded_data):
    client = Client()
    client.force_login(User.objects.get(email="admin@forbmax.local"))
    return client


@pytest.fixture
def member_client(seeded_data):
    client = Client()
    client.force_login(User.objects.get(email="member@forbmax.local"))
    return client


@pytest.fixture
def nimar_client(seeded_data):
    client = Client()
    client.force_login(User.objects.get(email="user@nimar.local"))
    return client
