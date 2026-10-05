from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Organization, User
from audit.models import ActivityLog
from django.conf import settings
from tracker.models import Module, Phase, Point, PointStatus


class Command(BaseCommand):
    help = "Seed Phase 1 organizations, users, phases, modules, and Demo Day sample points."

    @transaction.atomic
    def handle(self, *args, **options):
        forbmax, _ = Organization.objects.update_or_create(
            code=Organization.Code.FORBMAX,
            defaults={"name": "Forbmax", "is_active": True},
        )
        nimar, _ = Organization.objects.update_or_create(
            code=Organization.Code.NIMAR,
            defaults={"name": "NIMAR", "is_active": True},
        )
        self.stdout.write(self.style.SUCCESS("Organizations ready."))

        from datetime import date

        phases = [
            ("DEMO_DAY", "Demo Day", 1, True, date(2026, 9, 1), date(2026, 10, 15)),
            ("PCT_25", "25%", 2, True, date(2026, 10, 16), date(2026, 11, 30)),
            ("PCT_75", "75%", 3, True, date(2026, 12, 1), date(2027, 1, 31)),
            ("SLA", "SLA", 4, True, date(2027, 2, 1), date(2027, 7, 31)),
        ]
        phase_objs = {}
        for code, name, order, active, start, end in phases:
            obj, _ = Phase.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "sort_order": order,
                    "is_active": active,
                    "description": f"{name} delivery phase",
                    "start_date": start,
                    "end_date": end,
                },
            )
            phase_objs[code] = obj
        self.stdout.write(self.style.SUCCESS("Phases ready (Demo Day / 25% / 75% / SLA)."))

        modules = ["AI Assistant", "Core Platform", "Reporting", "Integrations"]
        module_objs = {}
        for name in modules:
            obj, _ = Module.objects.update_or_create(name=name, defaults={"is_active": True})
            module_objs[name] = obj
        self.stdout.write(self.style.SUCCESS("Modules ready."))

        admin_user, created = User.objects.get_or_create(
            email="admin@forbmax.local",
            defaults={
                "name": "Forbmax Admin",
                "organization": forbmax,
                "role": User.Role.FORBMAX_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if created or not admin_user.has_usable_password():
            admin_user.set_password(settings.SEED_ADMIN_PASSWORD)
            admin_user.save()
        else:
            # Keep role/org aligned on re-seed
            admin_user.organization = forbmax
            admin_user.role = User.Role.FORBMAX_ADMIN
            admin_user.is_staff = True
            admin_user.is_active = True
            admin_user.save()

        member, created = User.objects.get_or_create(
            email="member@forbmax.local",
            defaults={
                "name": "Forbmax Member",
                "organization": forbmax,
                "role": User.Role.FORBMAX_MEMBER,
                "is_active": True,
            },
        )
        if created or not member.has_usable_password():
            member.set_password(settings.SEED_MEMBER_PASSWORD)
            member.save()
        else:
            member.organization = forbmax
            member.role = User.Role.FORBMAX_MEMBER
            member.is_active = True
            member.save()

        nimar_user, created = User.objects.get_or_create(
            email="user@nimar.local",
            defaults={
                "name": "NIMAR User",
                "organization": nimar,
                "role": User.Role.NIMAR_USER,
                "is_active": True,
            },
        )
        if created or not nimar_user.has_usable_password():
            nimar_user.set_password(settings.SEED_NIMAR_PASSWORD)
            nimar_user.save()
        else:
            nimar_user.organization = nimar
            nimar_user.role = User.Role.NIMAR_USER
            nimar_user.is_active = True
            nimar_user.save()

        self.stdout.write(self.style.SUCCESS("Seed users ready (admin/member/nimar)."))

        demo = phase_objs["DEMO_DAY"]
        sample_points = [
            {
                "external_id": "A-001",
                "annexure": "A",
                "number": "1",
                "module": module_objs["AI Assistant"],
                "title": "Demo assistant greeting flow",
                "requirement": "Demonstrate AI assistant greeting and safe fallback responses.",
                "status": PointStatus.IN_PROGRESS,
                "owner": member,
            },
            {
                "external_id": "A-002",
                "annexure": "A",
                "number": "2",
                "module": module_objs["Core Platform"],
                "title": "Login and role isolation",
                "requirement": "Show authenticated access with Forbmax and NIMAR role separation.",
                "status": PointStatus.AWAITING_VERIFICATION,
                "owner": admin_user,
            },
            {
                "external_id": "B-001",
                "annexure": "B",
                "number": "1",
                "module": module_objs["Reporting"],
                "title": "Demo Day KPI strip",
                "requirement": "Provide control-room KPI summary for Demo Day points.",
                "status": PointStatus.PLANNED,
                "owner": member,
            },
        ]

        for data in sample_points:
            point, created = Point.objects.update_or_create(
                external_id=data["external_id"],
                defaults={
                    "organization": forbmax,
                    "annexure": data["annexure"],
                    "number": data["number"],
                    "module": data["module"],
                    "phase": demo,
                    "title": data["title"],
                    "requirement": data["requirement"],
                    "status": data["status"],
                    "owner": data["owner"],
                    "updated_by": admin_user,
                    "scope_approved": data["status"]
                    in {
                        PointStatus.IN_PROGRESS,
                        PointStatus.AWAITING_VERIFICATION,
                        PointStatus.REWORK_REQUESTED,
                        PointStatus.VERIFIED_CLOSED,
                    },
                    "notes": "Seeded Demo Day fixture",
                    "source_metadata": {"seed": True, "phase": "Demo Day"},
                },
            )
            if created:
                ActivityLog.objects.create(
                    actor=admin_user,
                    organization=forbmax,
                    entity_type="Point",
                    entity_id=point.external_id,
                    action="seed_create",
                    new_value={"status": point.status, "title": point.title},
                    message="Seeded Demo Day sample point",
                )

        self.stdout.write(self.style.SUCCESS("Demo Day sample points ready."))
        self.stdout.write(self.style.SUCCESS("Phase 1 seed complete."))
