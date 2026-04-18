# Este archivo se utiliza para utilidades generales y, principalmente, para la lógica clínica de VacunaTrack.
# Contiene el motor que evalúa las dosis de un paciente, basándose en reglas de negocio estrictas.
# También, contiene funciones generales (convertir fechas a texto legible, y generar contraseñas temporales.)

import random
import string
from datetime import date

# estados posibles de una dosis
STATUS_APLICADA     = 'aplicada'
STATUS_FALTANTE     = 'faltante'
STATUS_CERCA_LIMITE = 'cerca_limite'
STATUS_ATRASADA     = 'atrasada'
STATUS_APLICABLE    = 'aplicable'
STATUS_PROXIMA      = 'proxima'

STATUS_LABELS = {
    STATUS_APLICADA:     'Aplicada',
    STATUS_FALTANTE:     'Faltante',
    STATUS_CERCA_LIMITE: 'Cerca del límite',
    STATUS_ATRASADA:     'Atrasada',
    STATUS_APLICABLE:    'Aplicable',
    STATUS_PROXIMA:      'Próxima',
}

STATUS_COLORS = {
    STATUS_APLICADA:     '#16A34A',
    STATUS_FALTANTE:     '#7F1D1D',
    STATUS_CERCA_LIMITE: '#EA580C',
    STATUS_ATRASADA:     '#DC2626',
    STATUS_APLICABLE:    '#D97706',
    STATUS_PROXIMA:      '#2563EB',
}

# cuantos dias antes del limite para marcar "cerca del limite"
DIAS_PARA_ATRASADA = 30
DIAS_CERCA_LIMITE  = 15


# calcula el estado de una dosis segun la edad del paciente
# el orden de prioridad es: aplicada > faltante > cerca del limite > atrasada > aplicable > proxima
def calculate_dose_status(birth_date, dose, applied_date=None,
                           prev_status=None, prev_applied_date=None):

    today    = date.today()
    age_days = (today - birth_date).days

    recommended_age = dose.get('dosis_edad_oportuna_dias') or 0
    limit_age       = dose.get('dosis_limite_edad_dias')
    interval_min    = dose.get('dosis_intervalo_min_dias') or 0

    # 1. si ya fue aplicada, no importa nada mas
    if applied_date is not None:
        return STATUS_APLICADA

    # 2. faltante: si paso el limite de edad ya no se puede aplicar
    if limit_age is not None and age_days >= limit_age:
        return STATUS_FALTANTE

    # si la dosis anterior de la serie es faltante, esta tambien lo es (cascada)
    if prev_status == STATUS_FALTANTE:
        return STATUS_FALTANTE

    # 3. cerca del limite: quedan pocos dias para que ya no se pueda aplicar
    if limit_age is not None:
        days_to_limit = limit_age - age_days
        if 0 < days_to_limit <= DIAS_CERCA_LIMITE:
            return STATUS_CERCA_LIMITE

    # a partir de aqui, ya llego a la edad recomendada
    if age_days >= recommended_age:

        # para series, la dosis anterior debe estar aplicada y cumplir el intervalo
        is_in_series = prev_status is not None
        if is_in_series:
            prev_ok = (prev_status == STATUS_APLICADA and prev_applied_date is not None)
            if not prev_ok:
                # previa no aplicada, esta queda bloqueada
                return STATUS_PROXIMA
            days_since_prev = (today - prev_applied_date).days
            if days_since_prev < interval_min:
                return STATUS_PROXIMA

        # 4. atrasada: ya pasaron 30 dias desde la edad oportuna
        days_past_recommended = age_days - recommended_age
        if days_past_recommended >= DIAS_PARA_ATRASADA:
            return STATUS_ATRASADA

        # 5. aplicable: todo ok, se puede apliar
        return STATUS_APLICABLE

    # 6. proxima: todavia no llega a la edad recomendada
    return STATUS_PROXIMA


# agrega el estado calculado a cada fila del historial
def enrich_history(rows, birth_date):
    last_status_by_vacuna  = {}
    last_applied_by_vacuna = {}

    enriched = []
    for row in rows:
        app_ts = row.get('aplicacion_timestamp')
        if hasattr(app_ts, 'date'):
            applied_date = app_ts.date()
        elif isinstance(app_ts, date):
            applied_date = app_ts
        else:
            applied_date = None

        vacuna = row.get('vacuna_nombre', '')
        prev_status       = last_status_by_vacuna.get(vacuna)
        prev_applied_date = last_applied_by_vacuna.get(vacuna)

        status = calculate_dose_status(
            birth_date        = birth_date,
            dose              = row,
            applied_date      = applied_date,
            prev_status       = prev_status,
            prev_applied_date = prev_applied_date,
        )

        row['status']       = status
        row['status_label'] = STATUS_LABELS[status]
        row['status_color'] = STATUS_COLORS[status]
        row['edad_texto']   = days_to_human(row.get('dosis_edad_oportuna_dias'))

        # actualizamos el tracker para la siguiente dosis de esta vacuna
        last_status_by_vacuna[vacuna] = status
        if status == STATUS_APLICADA and applied_date:
            last_applied_by_vacuna[vacuna] = applied_date

        enriched.append(row)

    return enriched


# valida si se puede registrar una aplicación segun reglas clínicas de edad e intervalo.
# retorna (True, None) si es válida, o (False, 'mensaje de error') si no.
def validar_aplicacion(paciente, dosis, aplicaciones_previas):
    from datetime import date
    hoy      = date.today()
    birth    = paciente['paciente_fecha_nac']
    age_days = (hoy - birth).days

    edad_oportuna = dosis.get('dosis_edad_oportuna_dias', 0)
    limite_edad   = dosis.get('dosis_limite_edad_dias')
    intervalo_min = dosis.get('dosis_intervalo_min_dias', 0)

    # 1. Verificar que la edad este dentro de la ventana permitida
    if limite_edad is not None and age_days >= limite_edad:
        return False, (
            f'El paciente tiene {age_days} días de vida y el límite de edad para esta dosis '
            f'es {limite_edad} días. No se puede registrar la aplicación.'
        )

    if age_days < edad_oportuna:
        return False, (
            f'El paciente tiene {age_days} días de vida. La edad mínima recomendada '
            f'para esta dosis es {edad_oportuna} días.'
        )

    # 2. Verificar intervalo mínimo desde la dosis anterior de la misma vacuna
    if intervalo_min > 0:
        vacuna_id = dosis.get('vacuna_id')
        import data as _data
        dosis_misma_vacuna = {d['dosis_id'] for d in _data.DOSIS if d['vacuna_id'] == vacuna_id}
        apps_misma_vacuna = [
            a for a in aplicaciones_previas
            if a['paciente_id'] == paciente['paciente_id']
            and a['dosis_id'] in dosis_misma_vacuna
        ]
        if apps_misma_vacuna:
            ultima = max(apps_misma_vacuna, key=lambda a: a['aplicacion_timestamp'])
            ts = ultima['aplicacion_timestamp']
            fecha_ultima = ts.date() if hasattr(ts, 'date') else ts
            dias_transcurridos = (hoy - fecha_ultima).days
            if dias_transcurridos < intervalo_min:
                faltan = intervalo_min - dias_transcurridos
                return False, (
                    f'Deben transcurrir al menos {intervalo_min} días entre dosis de la misma vacuna. '
                    f'La última dosis fue hace {dias_transcurridos} días. Faltan {faltan} días.'
                )

    return True, None


# genera una contraseña temporal aleatoria para nuevos usuarios
def generate_temp_password(length=10):
    chars = string.ascii_letters + string.digits + '!@#$'
    return ''.join(random.choices(chars, k=length))


# convierte dias a texto legible, ej: 60 dias = "2 meses"
def days_to_human(days):
    if days is None:
        return '—'
    if days == 0:
        return 'Al nacer'
    if days < 30:
        return f'{days} día{"s" if days > 1 else ""}'
    if days < 365:
        months = days // 30
        return f'{months} mes{"es" if months > 1 else ""}'
    years  = days // 365
    months = (days % 365) // 30
    base   = f'{years} año{"s" if years > 1 else ""}'
    return f'{base} {months} mes{"es" if months > 1 else ""}' if months else base
