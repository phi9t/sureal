FROM sureal-association41-base-training:46bdaa6e8d90
COPY runtime_requirements.lock /opt/association-requirements.lock
RUN uv pip install --python /opt/waymo/bin/python --require-hashes -r /opt/association-requirements.lock
