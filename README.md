# reverse-sshfs

`sshfs` の slave mode <!-- 名前の苦情は upstream へ --> と `sftp-server` を利用し、ローカルのファイルシステムをリモートにマウントするスクリプトです。`sshfs` はリモートのファイルシステムをローカルにマウントするものなので、その逆ということで `reverse-sshfs` という名前を付けています。

**⚠️DISCLAIMER**: このスクリプトには、絶対パスでのアクセス等で想定しない位置のファイルが書き換えられないように、 sftp の内容を覗き見て変なパスだったら Permission Denied を返す機能が搭載されています。**しかし、この機能は `sftp-server` の実装によっては `SSH_FXP_EXTENDED` 等により迂回でき、また場合によってうまく保護機能が動作しない可能性があるため、信頼できないリモートホストにこのスクリプトを利用するべきではありません。**

## Usage

`reverse-sshfs.py /path/to/local/path remote-host /path/to/remote/path`