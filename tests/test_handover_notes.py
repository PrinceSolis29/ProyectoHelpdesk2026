import pytest

from app.domain.errors import PermissionDeniedError, ValidationError
from app.models.enums import CATEGORIES, PRIORITIES, Role
from app.repositories.sqlalchemy import SqlAlchemyTicketRepository, SqlAlchemyUserRepository
from app.services.tickets import TicketService
from app.services.users import UserService

VALID_CATEGORY = next(iter(CATEGORIES))
VALID_PRIORITY = next(iter(PRIORITIES))


def test_handover_notes_unit_flow(world):
    ticket = world.tickets.create(
        requester_id=world.requester.id,
        title="Falla en proyector aula 4",
        description="No enciende al conectar HDMI",
        category=VALID_CATEGORY,
        priority=VALID_PRIORITY,
    )

    note = world.tickets.add_handover_note(
        ticket.id,
        author=world.technician,
        body="Se revisa cable HDMI; pendiente cambio de adaptador en siguiente turno.",
    )
    assert note.author_id == world.technician.id
    assert note.body == "Se revisa cable HDMI; pendiente cambio de adaptador en siguiente turno."

    notes_for_supervisor = world.tickets.list_handover_notes(world.supervisor, ticket.id)
    assert len(notes_for_supervisor) == 1
    first_note = next(iter(notes_for_supervisor))
    assert "cambio de adaptador" in first_note.body

    with pytest.raises(PermissionDeniedError):
        world.tickets.add_handover_note(
            ticket.id,
            author=world.requester,
            body="Intento de solicitante",
        )

    with pytest.raises(PermissionDeniedError):
        world.tickets.list_handover_notes(world.requester, ticket.id)


def test_handover_notes_persistence_and_rejection(db):
    user_repo = SqlAlchemyUserRepository(db)
    ticket_repo = SqlAlchemyTicketRepository(db)
    users = UserService(user_repo)
    service = TicketService(ticket_repo, users)

    requester = users.register("Ana Solicitante", "ana.test@school.edu", Role.REQUESTER)
    tech1 = users.register("Luis Tecnico", "luis.test@school.edu", Role.TECHNICIAN)
    supervisor = users.register("Carla Supervisora", "carla.test@school.edu", Role.SUPERVISOR)

    ticket = service.create(
        requester_id=requester.id,
        title="Sin internet en laboratorio",
        description="Switch sin enlace",
        category=VALID_CATEGORY,
        priority=VALID_PRIORITY,
    )

    created = service.add_handover_note(
        ticket.id,
        author=tech1,
        body="Puerto 12 reiniciado; revisar patch panel.",
    )
    db.flush()

    # Otro miembro tecnico consulta desde PostgreSQL y ve la nota persistida
    notes = service.list_handover_notes(supervisor, ticket.id)
    assert len(notes) == 1
    persisted = next(iter(notes))
    assert persisted.id == created.id
    assert persisted.body == "Puerto 12 reiniciado; revisar patch panel."

    # Solicitante es rechazado y no muta el estado ni agrega notas
    with pytest.raises(PermissionDeniedError):
        service.add_handover_note(ticket.id, author=requester, body="Nota no autorizada")

    with pytest.raises(ValidationError):
        service.add_handover_note(ticket.id, author=tech1, body="   ")

    assert len(service.list_handover_notes(tech1, ticket.id)) == 1
