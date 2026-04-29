pkgname=howdy-surface
pkgver=0.1.0
pkgrel=1
pkgdesc="Microsoft Surface IR camera helper for Howdy with optional FIDO2 PAM support"
arch=('any')
url="https://github.com/offyotto/howdy-surface"
license=('MIT')
depends=('python' 'howdy-git' 'ffmpeg' 'v4l-utils')
optdepends=(
  'pam-u2f: FIDO2/U2F passkey-style PAM authentication'
  'libfido2: FIDO2 token management and browser security-key support'
  'hyprlock: Hyprland lock screen integration'
)
install=howdy-surface.install
source=(
  "howdy-surface.py"
  "README.md"
  "SECURITY.md"
  "PASSKEYS.md"
  "AUR.md"
  "LICENSE"
)
sha256sums=('1ed59c1ec426246c9f313b4595c59f0cccd398b50fd768410558155b2d684e6d'
            'acd826ed695a818ba8060f69ea766bb5ed34a5e65265eb700c16baac763a3f8a'
            '87b09167f83f44ebc399cf2b12cfb0056579bdc06a28cd95f09d89af63476157'
            '35a86bb024f69999313f2736ad9a517c67e0a36dee78972288caf81b5d125d4d'
            '791e2d9690d140f187578411c74b8d0b9659e64985d3697e1dc1ef0b46fae313'
            'e6ec4e0e693e534d6ce8f566177b8c7081c232bf52775f1c431962a8c1254996')

package() {
  install -Dm755 "$srcdir/howdy-surface.py" "$pkgdir/usr/bin/howdy-surface"
  install -Dm644 "$srcdir/README.md" "$pkgdir/usr/share/doc/howdy-surface/README.md"
  install -Dm644 "$srcdir/SECURITY.md" "$pkgdir/usr/share/doc/howdy-surface/SECURITY.md"
  install -Dm644 "$srcdir/PASSKEYS.md" "$pkgdir/usr/share/doc/howdy-surface/PASSKEYS.md"
  install -Dm644 "$srcdir/AUR.md" "$pkgdir/usr/share/doc/howdy-surface/AUR.md"
  install -Dm644 "$srcdir/LICENSE" "$pkgdir/usr/share/licenses/howdy-surface/LICENSE"
}
