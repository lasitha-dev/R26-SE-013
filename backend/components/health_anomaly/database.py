from core.database import db

# ==============================================================================
# HEALTH ANOMALY COMPONENT - DATABASE COLLECTIONS
# ------------------------------------------------------------------------------
# What this file does:
#   Connects to the MongoDB database and defines references to each collection
#   used by the Animal Health Anomaly, Persistent Monitoring & BCS module.
#
# Why we need it:
#   Centralizing database collections in one file ensures clean code, prevents
#   typos in collection names, and allows easy database queries across the router.
# ==============================================================================

# 1. Farms Collection: Stores registered farm accounts, owners, and GPS locations
farms_collection = db.farms

# 2. Cattle Collection: Stores individual animal profiles (Ear tag, breed, DOB, weight, status)
cattles_collection = db.cattle

# 3. Daily Logs Collection: Stores everyday intake data (milk yield, weight, water, feed, temp)
daily_logs_collection = db.daily_logs

# 4. Breed Settings Collection: Stores custom benchmark averages (milk yield, weight) per breed
breed_settings_collection = db.breed_settings

# 5. BCS Logs Collection: Stores Body Condition Score results and Grad-CAM visual explanation links
bcs_logs_collection = db.bcs_logs

# 6. Vets Collection: Stores registered Veterinarian accounts and their assigned districts/farms
vets_collection = db.vets

# 7. Diagnostic Cases Collection: Stores disease diagnosis cases submitted for veterinary review
diagnostic_cases_collection = db.diagnostic_cases

# 8. Death Logs Collection: Stores mortality records (cause of death: FMD, LSD, or other)
death_logs_collection = db.death_logs

# 9. Vet Notifications Collection: Stores alerts sent to veterinarians when high-risk cases occur
vet_notifications_collection = db.vet_notifications



