ARG DEBIAN_RELEASE="bookworm"
FROM mcr.microsoft.com/devcontainers/python:3.11-${DEBIAN_RELEASE}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iputils-ping

# RUN python -m pip install --upgrade pip

# Create non-root user
ARG USERNAME=vscode

# Install Starship
RUN curl -sS https://starship.rs/install.sh | sh -s -- --yes

# Set up Starship for the vscode user
RUN echo 'eval "$(starship init bash)"' >> /home/$USERNAME/.bashrc \
    && mkdir -p /home/$USERNAME/.config \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME/.config \
    && chown $USERNAME:$USERNAME /home/$USERNAME/.bashrc


