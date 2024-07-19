from fastapi import FastAPI
from pydantic import BaseModel
from hasura_chris_poc.global_client import pl_dircopy as get_pl_dircopy
import os.path

app = FastAPI()

class ReceivedDicom(BaseModel):
    fname: str


@app.post("/handle_dicom/")
async def handle_dicom(dicom: ReceivedDicom) -> str:
    if "org.fnndsc.oxidicom" in dicom.fname:
        return "SKIP"
    pl_dircopy = await get_pl_dircopy()
    plinst = await pl_dircopy.create_instance(dir=os.path.dirname(dicom.fname))
    feed = await plinst.get_feed()
    await feed.set(name=f'Auto-event for "{os.path.basename(dicom.fname)}"')
    return "OK"
