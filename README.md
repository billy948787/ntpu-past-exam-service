# 北大考古題 NTPU Past Exam Backend

## Tech Stack

- **Framework**: [Fast api](https://fastapi.tiangolo.com/)
- **Deployment**: [GCP](https://cloud.google.com/?hl=
- **Monitor**: [Better Stack](https://betterstack.com/)
- **Static File**: Cloudflare R2
- **Database**: PlanetScale

## Start dev server

1. Create a ".env" file in root folder. It should contain following key:

```
DATABASE_HOST=
DATABASE_USERNAME=
DATABASE_PASSWORD=
DATABASE=
DATABASE_PORT=

R2_ACCESS_TOKEN=
R2_ACCESS_KEY=
R2_URL=
R2_BUCKET_NAME=
R2_FILE_PATH=

AWS_EMAIL_SENDER=
AWS_ACCESS_KEY=
AWS_ACCESS_SECRET=

ORIGIN=
HASH_KEY=
LOG_TAIL_SOURCE_KEY=
#
REDIS_CONNECTION_STRING=
#
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=

GOOGLE_SERVICE_SECRET=
GOOGLE_SERVICE_CLIENT_ID=
```

You should get the value from the code owner. 2. Install dependancies:

```shell
uv sync
source .venv/bin/activate
```

3. Start dev server

```shell
uvicorn main:app --reload
```

## Start Dev server using Docker

```shell
docker-compose up --build
```

You will still need to create a `.env` file in the root folder as described above.
But the database and redis server will be created automatically using docker-compose.
