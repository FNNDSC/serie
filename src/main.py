from serie import router, __version__
from fastapi import FastAPI


app = FastAPI(
    title="Specific Endpoints for Research Integration Events",
    contact={
        "name": "FNNDSC",
        "url": "https://chrisproject.org",
        "email": "Newborn_FNNDSCdev-dl@childrens.harvard.edu",
    },
    version=__version__,
)
app.include_router(router)
