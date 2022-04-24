set -euo pipefail

IMAGE=myforest/heatpump-act-test

DOCKER_BUILDKIT=1 docker build --tag ${IMAGE} .

. .env

docker run \
--rm \
--env-file .env \
-v ${STATE}:/state/:ro \
-v ${WEATHER}:/weather:ro \
${IMAGE} \
$@