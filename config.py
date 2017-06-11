# coding: utf8
import datetime

# Maximale Arbeitszeit während einer Dienstreise
# Sekunden, Mikro-Sek., Milli-Sek. -----v--v--v  v------ Minuten
# Tage ------------------------------v  |  |  |  |   v-- Stunden
max_dienstreise = datetime.timedelta(0, 0, 0, 0, 0, 12)

# Maximale Arbeitszeit bei normaler Anwesenheit
max_anwesenheit = datetime.timedelta(0, 0, 0, 0, 0, 10)

# Frühester Arbeitsbeginn
# Uhrzeit ---------------------> HH: MM
min_von_anwesend = datetime.time( 6, 15)

# Spätestes Arbeitsende
max_bis_anwesend = datetime.time(19, 45)

# Minimale Erholung zwischen zwei aufeinanderfolgenden Arbeitstagen
min_erholung = datetime.timedelta(0, 0, 0, 0, 0, 11)
