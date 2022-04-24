# This is a multi-stage Dockerfile, it may look a bit complicated because it's trying to do so many interconnected things
# See build.sh for how to run it

# First of all, let's get a nice Python environment
FROM python:3.9 as core

RUN touch /tmp/one_ring_to_bind_them_all

WORKDIR /app/


RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
RUN poetry --version

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install --no-root

#-------------------
FROM core as collect_source

COPY act/*.py act/

#-------------------
FROM core as check_types_make_sense


COPY --from=collect_source /app/act act

COPY lint/ act/lint/
RUN poetry run mypy -p act --config-file act/lint/mypy.ini

COPY .pylintrc .
RUN poetry run pylint act/

#-------------------
FROM core as check_formatting_is_reasonable

COPY --from=collect_source /app/act act

RUN poetry run black --check --diff act/


#-------------------
FROM core as run_all_the_unit_tests

COPY --from=collect_source /app/act act

COPY test act/test

RUN poetry run pytest --numprocesses=auto


#-------------------
FROM collect_source as check_the_program_is_basically_functional

RUN poetry run python -m act.act --help | grep "heatpump"


#-------------------
# Now reference all the targets in a single step so they all get run before we produce this output
FROM collect_source as runtime

COPY --from=check_types_make_sense /tmp/one_ring_to_bind_them_all /tmp/
COPY --from=check_formatting_is_reasonable /tmp/one_ring_to_bind_them_all /tmp/
COPY --from=run_all_the_unit_tests /tmp/one_ring_to_bind_them_all /tmp/
COPY --from=check_the_program_is_basically_functional /tmp/one_ring_to_bind_them_all /tmp/

ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"
ENTRYPOINT ["poetry","run","python","-m","act.act","--dry-run" ]