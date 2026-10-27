# Package init — do NOT import app.main here; it has side effects
# (lifespan handlers, Firebase init, model loading) and causes circular
# imports when submodules try to import from app.config or app.models.
