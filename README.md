# SERIE -- _ChRIS_

[![Version](https://img.shields.io/docker/v/fnndsc/serie?sort=semver)](https://hub.docker.com/r/fnndsc/serie)
[![Tests](https://github.com/FNNDSC/serie/actions/workflows/test.yml/badge.svg)](https://github.com/FNNDSC/serie/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/FNNDSC/serie/graph/badge.svg?token=PU0WZLNL02)](https://codecov.io/gh/FNNDSC/serie)

The _Specific Endpoints for Research Integration Events_, or _SERIE_,
is a [FastAPI](https://fastapi.tiangolo.com/) application which defines
the business logic of event-driven _ChRIS_ use cases. E.g. it handles
use cases such as "for every DICOM series received with the description
'Hips to Ankles' create a new feed and run the
[leg length discrepancy (LLD) analysis pipeline](https://github.com/FNNDSC/pl-dylld)."

## How It Works

_SERIE_ should be called on by an instance of [Hasura](https://hasura.io/) via its
"events" feature, listening to the PostgreSQL database of the _ChRIS_ backend (_CUBE_).

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
docker compose --profile hasura up -d
```

### Testing

Run unit tests on-the-metal:

```shell
rye run pytest
```

Integration and end-to-end tests require _SERIE_ to run in the same docker network as _CUBE_ and Hasura.
First, run [miniChRIS-docker](https://github.com/FNNDSC/miniChRIS-docker) to get _CUBE_ and Hasura up,
then run pytest and _SERIE_ using Docker Compose:

```shell
docker compose run --rm --use-aliases test
```

### Deployment Notes

- The only environment variable needed by _SERIE_ is `CHRIS_HOST`, which should be set
  to the API host of _CUBE_, e.g. `https://cube.chrisproject.org/`
- The configuration of _SERIE_ happens in Hasura. You can use the Hasura console to
  edit the configuration, or use [hasura-cli](https://hasura.io/docs/latest/hasura-cli/overview/)
  configure _SERIE_ via Hasura metadata YAML files. See the example in
  [hasura/.../public_pacsfiles_pacsseries.yaml](hasura/metadata/databases/chris/tables/public_pacsfiles_pacsseries.yaml).
