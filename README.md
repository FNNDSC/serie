# SERIE -- _ChRIS_

The _Specific Endpoints for Research Integration Events_, or _SERIE_,
is a [FastAPI](https://fastapi.tiangolo.com/) application which defines
the business logic of event-driven _ChRIS_ use cases. E.g. it handles
use cases such as "for every DICOM series received with the description
'Hips to Ankles' create a new feed and run the
[leg length discrepancy (LLD) analysis pipeline](https://github.com/FNNDSC/pl-dylld)."

## How It Works

_SERIE_ should be called on by an instance of [Hasura](https://hasura.io/)
listening to the PostgreSQL database of the _ChRIS_ backend (_CUBE_).

[![Architecture Diagram](https://chrisproject.org/assets/images/ChRIS_architecture-febf870b69ec83221fa0ede8e6b70447.svg)](https://chrisproject.org/docs/architecture)

The LLD pipeline works like this:

1. PACS --[DICOM image data]--> [oxidicom](https://github.com/FNNDSC/oxidicom)
2. oxidicom --[registers file to]--> PostgreSQL
3. PostgreSQL --[event detected by]--> Hasura
4. Hasura --[HTTP request: handle event]--> _SERIE_
5. _SERIE_ --[HTTP request: run workflow]--> _CUBE_

## Development

Install [rye](https://rye.astral.sh) and run

```shell
rye sync
```

For local testing, run _ChRIS_ locally with Hasura.

```shell
cd
git clone https://github.com/FNNDSC/miniChRIS-docker.git
cd miniChRIS-docker
./minichris.sh
docker compose --profile hasura up -d
```

### Testing

Run unit tests on-the-metal:

```shell
rye run pytest
```

End-to-end tests require _SERIE_ to run in the same docker network as _CUBE_ and Hasura,
so we need to run them with Docker Compose:

```shell
docker compose run test
```

### Deployment

See https://github.com/FNNDSC/charts
