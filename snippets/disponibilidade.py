# Trecho curado do Planejador (repositório privado)
# Origem: backend/apps/appointments/selectors.py
#
# Motor de disponibilidade: dado um profissional, uma data e um serviço,
# calcula os horários livres respeitando a jornada de trabalho, as exceções
# (folgas/horários especiais) e os agendamentos já existentes — descartando
# slots no passado e fazendo encaixe sequencial. Fica em `selectors.py`
# (padrão selectors/services), o que mantém as views finas e a regra de
# negócio testável sem subir um request HTTP.

from datetime import datetime, timedelta

from django.utils import timezone

from apps.core.utils import BUSINESS_TZ
from apps.professionals.models import ScheduleException, WorkSchedule

from .models import Appointment


def _windows_for_date(professional, date):
    """
    Janelas (start_time, end_time) em que o profissional atende na data,
    considerando exceções:
      - ScheduleException is_closed=True  → folga (nenhuma janela).
      - ScheduleException is_closed=False → janela especial da exceção.
      - Sem exceção → WorkSchedule(s) do dia da semana.
    """
    exception = ScheduleException.objects.filter(
        professional=professional, date=date
    ).first()
    if exception is not None:
        if exception.is_closed:
            return []
        return [(exception.start_time, exception.end_time)]

    schedules = WorkSchedule.objects.filter(
        professional=professional, day_of_week=date.weekday()
    ).order_by('start_time')
    return [(s.start_time, s.end_time) for s in schedules]


def get_available_slots(professional, date, service_type):
    """
    Calcula os horários livres de um profissional numa data para um serviço.

    Encaixe sequencial: cada slot começa quando o anterior (ou o agendamento
    existente) termina; o slot dura `service_type.duration_minutes`. Slots no
    passado são descartados. Retorna uma lista de datetimes UTC (aware) de início.
    """
    duration = timedelta(minutes=service_type.duration_minutes)
    now = timezone.now()

    # Agendamentos que ainda ocupam a agenda nesse dia, em UTC.
    day_start = datetime.combine(date, datetime.min.time(), tzinfo=BUSINESS_TZ)
    day_end = day_start + timedelta(days=1)
    busy = list(
        Appointment.objects.filter(
            professional=professional,
            status__in=Appointment.ACTIVE_STATUSES,
            start_datetime__lt=day_end,
            end_datetime__gt=day_start,
        ).values_list('start_datetime', 'end_datetime')
    )

    slots = []
    for start_time, end_time in _windows_for_date(professional, date):
        cursor = datetime.combine(date, start_time, tzinfo=BUSINESS_TZ)
        window_end = datetime.combine(date, end_time, tzinfo=BUSINESS_TZ)

        while cursor + duration <= window_end:
            slot_end = cursor + duration
            overlaps = any(b_start < slot_end and cursor < b_end for b_start, b_end in busy)
            if not overlaps and cursor >= now:
                slots.append(cursor)
                cursor = slot_end
            elif overlaps:
                # Avança até o fim do agendamento que conflita (encaixe sequencial).
                conflict_end = max(
                    b_end for b_start, b_end in busy if b_start < slot_end and cursor < b_end
                )
                cursor = conflict_end
            else:
                # Slot no passado — avança um passo de duração.
                cursor = slot_end

    return slots
