set -euo pipefail

IMAGE=myforest/heatpump-act-test

DOCKER_BUILDKIT=1 docker build --tag ${IMAGE} .

. .env

set -x
docker run \
--rm \
-v ${STATE}:/state/:ro \
-v ${WEATHER}:${WEATHER}:ro \
${IMAGE} \
python -m act.act --dry-run $@