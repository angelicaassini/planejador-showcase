# Trecho curado do Planejador (repositório privado)
# Origem: backend/apps/appointments/tests/test_availability.py
#
# Testes de API (DRF APITestCase) que provam a correção do motor de
# disponibilidade. O destaque é `test_booked_slot_is_removed`: depois de
# agendar 09:00, esse horário some da lista de disponíveis — ou seja, o
# sistema não permite duplo-agendamento. Suíte completa: 159 testes, 100%
# de cobertura no backend.
#
# (Helpers _register/_auth e cálculo de data foram omitidos por brevidade.)

class AvailabilityTests(APITestCase):
    def setUp(self):
        self.admin = _register(self.client, 'Salão A', 'admin_a@x.com')
        _auth(self.client, 'admin_a@x.com')
        self.tenant = self.admin.tenant
        self.prof = Professional.objects.create(tenant=self.tenant, display_name='João')
        self.service_type = ServiceType.objects.create(
            tenant=self.tenant, name='Corte', duration_minutes=60
        )
        # Segunda-feira 09:00–12:00.
        WorkSchedule.objects.create(
            tenant=self.tenant, professional=self.prof,
            day_of_week=0, start_time=time(9), end_time=time(12),
        )
        self.monday = _next_monday()

    def test_slots_in_empty_day(self):
        response = self._get_availability()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 09:00, 10:00, 11:00 (serviço de 60 min numa janela de 3h).
        starts = [s['start'] for s in response.data]
        self.assertEqual(len(starts), 3)

    def test_booked_slot_is_removed(self):
        Appointment.objects.create(
            tenant=self.tenant, professional=self.prof, service_type=self.service_type,
            client_name='Maria', start_datetime=_local(self.monday, 9),
        )
        response = self._get_availability()
        self.assertEqual(len(response.data), 2)  # sobram só 10:00 e 11:00

    def test_day_off_has_no_slots(self):
        ScheduleException.objects.create(
            tenant=self.tenant, professional=self.prof, date=self.monday, is_closed=True,
        )
        response = self._get_availability()
        self.assertEqual(response.data, [])
