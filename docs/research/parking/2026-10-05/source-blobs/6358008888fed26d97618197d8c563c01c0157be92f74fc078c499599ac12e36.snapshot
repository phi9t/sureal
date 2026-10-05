FROM python@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
COPY requirements.lock /opt/collaboration/requirements.lock
COPY packages/ /opt/collaboration/packages/
RUN python -c 'import hashlib,json,pathlib; p=pathlib.Path("/opt/collaboration"); pins=json.loads((p/"requirements.lock").read_text())["debian_packages"]; files={x.name:x for x in (p/"packages").glob("*.deb")}; assert set(files)==set(pins); assert all(hashlib.sha256(files[k].read_bytes()).hexdigest()==v["sha256"] for k,v in pins.items())' \
    && dpkg -i /opt/collaboration/packages/*.deb \
    && python -c 'import sys; assert sys.version_info[:3] == (3,12,14)' \
    && git --version \
    && mkdir -p /experiment /source /outputs \
    && rm -rf /opt/collaboration/packages
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
