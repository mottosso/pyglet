FROM ubuntu:16.04

# Needed to install pyside2-tools without issues
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && \
    apt-get install -y \
        software-properties-common && \
    add-apt-repository -y ppa:thopiekar/pyside-git && \
    apt-get update && apt-get install -y \
        python3 \
        python3-dev \
        python3-pip \
        python3-pyqt4 \
        python3-pyqt5 \
        python3-pyside \
        python3-pyside2 \
        pyside2-tools \
        xvfb

RUN pip3 install \
    pytest \
    sphinx \
    pytest-cov \
    Pillow wheel

# Xvfb
# Enable "fake" display, such that pyglet can go ahead
# and create windows and read from them as though they
# were made on a computer with a display
ENV DISPLAY :99

WORKDIR /workspace
ENTRYPOINT Xvfb :99 -screen 0 1024x768x16 2>/dev/null & \
    while ! ps aux | grep -q '[0]:00 Xvfb :99 -screen 0 1024x768x16'; \
        do echo "Waiting for Xvfb..."; sleep 1; done && \
    echo "#\n# Unit testing.." && \
        python3 -u -m pytest && \
    echo Done