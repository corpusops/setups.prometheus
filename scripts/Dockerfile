FROM corpusops/ubuntu-bare:20.04
WORKDIR /tmp/install
ARG DEV_DEPENDENCIES_PATTERN='^#\s*dev dependencies' \
    PY_VER=3.8 \
    USER_NAME=app USER_UID=1000 USER_GROUP= USER_GID= \
    USER_HOME=/w
ARG PIP_SRC=$USER_HOME/lib
ENV USER_NAME=$USER_NAME USER_GROUP=${USER_GROUP:-$USER_NAME} USER_UID=$USER_UID USER_GID=${USER_GID:-${USER_UID}} USER_HOME=$USER_HOME PY_VER=${PY_VER:-} PIP_SRC=$PIP_SRC

# system dependendencies (pkgs, users, etc)
ADD apt*.txt ./
RUN set -e \
  && if !( getent group  $USER_NAME 2>/dev/null);then groupadd -g $USER_GID $USER_NAME;fi \
  && if !( getent passwd $USER_NAME 2>/dev/null);then \
    useradd -s /bin/bash -d $USER_HOME -m -u $USER_UID -g $USER_UID $USER_NAME;fi \
  && sed -i -re "s/(python-?)[0-9]\.[0-9]+/\1$PY_VER/g" apt.txt \
  && apt update && apt install -y $(egrep -v "^#" apt.txt) \
  && mkdir -pv "$PIP_SRC" && chown $USER_NAME "$PIP_SRC" \
  && printf "$USER_NAME ALL=(ALL) NOPASSWD:ALL\n">/etc/sudoers.d/app \
  && : end

WORKDIR $USER_HOME

ENV PATH=$USER_HOME/node_modules/.bin:$USER_HOME/bin:$PATH

# install python app
ARG REQUIREMENTS=requirements/requirements.txt requirements/requirements-dev.txt
ENV REQUIREMENTS=$REQUIREMENTS
ADD --chown=app:app lib/ lib/
ADD --chown=app:app src/ src/
ADD --chown=app:app *.py *txt *md *in ./
ADD --chown=app:app requirements/requirement*txt requirements/
RUN bash -c 'set -e \
  && for i in / /usr /usr/local;do \
  ln -fsv $(which python${PY_VER}) $i/bin/python;done \
  && python <(curl https://bootstrap.pypa.io/get-pip.py) \
  && python -m pip install --no-cache -r <( cat $REQUIREMENTS ) \
  && chown -Rf $USER_NAME .'

# final cleanup
RUN \
  set -ex \
  && sed -i -re "s/(python-?)[0-9]\.[0-9]+/\1$PY_VER/g" apt.txt \
  && apt install $(dpkg -l|awk '{print $2}'|grep -v -- -dev|egrep python.?-) \
  && if $(egrep -q "${DEV_DEPENDENCIES_PATTERN}" apt.txt);then \
    apt-get remove --auto-remove --purge \
  $(sed "1,/${DEV_DEPENDENCIES_PATTERN}/ d" apt.txt|grep -v '^#'|tr "\n" " ");\
  fi \
  && rm -rf /var/lib/apt/lists/* /tmp/install
# run settings
ADD --chown=app:app bin/ bin/
CMD []
ENTRYPOINT ["docker-entrypoint.sh"]
