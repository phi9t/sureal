FROM sureal-association41-base-cpu:e796dd50d006
COPY requirements.lock /opt/association-requirements.lock
RUN python -m pip install --require-hashes -r /opt/association-requirements.lock
