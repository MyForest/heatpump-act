# This is a multi-stage Dockerfile, it may look a bit complicated because it's trying to do so many interconnected things
# See build.sh for how to run it

# First of all, let's get a nice Python environment
FROM python as core

RUN touch /tmp/one_ring_to_bind_them_all

WORKDIR /app/

COPY requirements.txt .

RUN pip install -r requirements.txt && rm requirements.txt

#-------------------
FROM core as collect_source

COPY act/*.py act/
COPY act/log4j.properties act/

#-------------------
FROM core as check_types_make_sense

RUN pip install mypy

COPY --from=collect_source /app/act act

COPY lint/ act/lint/
RUN mypy -p act --config-file act/lint/mypy.ini

COPY .pylintrc .
RUN pylint act/

#-------------------
FROM core as check_formatting_is_reasonable

RUN pip install black
RUN pip list | grep black

COPY pyproject.toml .

COPY --from=collect_source /app/act act

RUN black --version && black --check --diff act/


#-------------------
FROM core as run_all_the_unit_tests

RUN pip install pytest pytest-xdist

COPY --from=collect_source /app/act act

COPY test act/test

RUN pytest --numprocesses=auto


#-------------------
FROM collect_source as check_the_program_is_basically_functional

RUN  python -m act.act --help | grep "heatpump"


#-------------------
# Now reference all the targets in a single step so they all get run before we produce this output
FROM collect_source as runtime

COPY --from=check_types_make_sense /tmp/one_ring_to_bind_them_all /tmp/
COPY --from=check_formatting_is_reasonable /tmp/one_ring_to_bind_them_all /tmp/
COPY --from=run_all_the_unit_tests /tmp/one_ring_to_bind_them_all /tmp/
COPY --from=check_the_program_is_basically_functional /tmp/one_ring_to_bind_them_all /tmp/