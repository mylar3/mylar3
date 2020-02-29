FROM python:3.8
# Debian Buster based Python image
# Alpine 3.11 fails to build PyQt5-sip, a comictagger dependancy.

# set version label
ARG MYLAR_COMMIT

RUN \
echo "**** install system packages ****" && \
 apt-get update && \
 apt-get install -y --no-install-recommends \
    nodejs=10.15.2~dfsg-2 && \
 echo "**** cleanup ****" && \
 apt-get -y clean && \
 rm -rf \
    /var/lib/apt/lists/* \
    /root/.cache \
    /tmp/*

# It might be better to check out release tags than python3-dev HEAD.
# For development work I reccomend mounting a full git repo from the
# docker host.
RUN echo "**** install app ****" && \
 git clone https://github.com/mylar3/mylar3.git --depth 1 --branch ${MYLAR_COMMIT:-python3-dev} --single-branch /app/mylar

RUN echo "**** install requirements ****" && \
 pip3 install --no-cache-dir -U -r /app/mylar/requirements.txt && \
 rm -rf ~/.cache/pip/*

# ports and volumes
VOLUME /config /comics /downloads
EXPOSE 8090
CMD ["python3", "/app/mylar/Mylar.py", "--nolaunch", "--quiet", "--datadir", "/config/mylar"]
