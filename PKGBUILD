# Maintainer: Arch Linux Engineering <devs@archlinux.org>
pkgname=arch-task-manager
_pkgname=arch_task
pkgver=1.0.0
pkgrel=1
pkgdesc="Native, high-performance GTK4 system and task manager for Arch Linux"
arch=('any')
url="https://archlinux.org"
license=('GPL3')
depends=(
    'python'
    'gtk4'
    'libadwaita'
    'python-gobject'
    'python-cairo'
    'systemd'
)
optdepends=(
    'smartmontools: Drive SMART health status monitoring'
    'nvidia-utils: NVIDIA GPU utilization and VRAM monitoring'
    'lm_sensors: Advanced motherboard fan speed and voltage monitoring'
    'xorg-xprop: X11 window click-to-kill target identification'
    'polkit: Privilege elevation for root process termination and systemd actions'
)
makedepends=('python-setuptools')
source=()
sha256sums=()

build() {
    cd "${srcdir}/.." || return 1
    python setup.py build
}

package() {
    cd "${srcdir}/.." || return 1
    python setup.py install --root="${pkgdir}" --optimize=1
}
