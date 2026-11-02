# Moduł 2: Bezpieczny serwer

## Cel
Zabezpieczyć lab01 jak serwer produkcyjny: logowanie tylko kluczem SSH, firewall, ochrona przed atakami na hasła, automatyczne aktualizacje i ukrycie wersji serwera WWW.

## Wykonane kroki
1. Utworzenie pary kluczy SSH na komputerze hosta (Windows):
   `ssh-keygen -t ed25519 -C "mbaron@windows"`
   Klucz prywatny zabezpieczony hasłem (passphrase) zostaje na hoście, klucz publiczny trafia na serwer.
2. Wgranie klucza publicznego na serwer z PowerShella:
   `type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh -p 2222 mbaron@127.0.0.1 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"`
3. Konfiguracja klienta SSH na hoście, żeby łączyć się skrótem `ssh lab01`.
4. Wyłączenie logowania hasłem i logowania jako root w osobnym pliku konfiguracyjnym serwera SSH, test konfiguracji i restart usługi.
5. Firewall ufw: domyślnie blokowany cały ruch przychodzący, otwarte tylko SSH (22) i HTTP (80).
6. fail2ban: automatyczne blokowanie adresów po 5 nieudanych próbach logowania w ciągu 10 minut, blokada na godzinę.
7. Sprawdzenie automatycznych aktualizacji bezpieczeństwa (unattended-upgrades).
8. Ukrycie wersji Nginx w nagłówkach odpowiedzi (`server_tokens off`).

## Konfiguracja

| Plik | Gdzie | Rola |
| --- | --- | --- |
| `~/.ssh/id_ed25519`, `~/.ssh/id_ed25519.pub` | host | klucz prywatny i publiczny |
| `~/.ssh/config` | host | skrót połączenia `lab01` |
| `~/.ssh/authorized_keys` | lab01 | lista kluczy, którym serwer ufa |
| `/etc/ssh/sshd_config.d/01-hardening.conf` | lab01 | zabezpieczenia serwera SSH ([kopia](../../config/lab01/ssh/01-hardening.conf)) |
| `/etc/fail2ban/jail.local` | lab01 | ustawienia fail2ban ([kopia](../../config/lab01/fail2ban/jail.local)) |
| `/etc/apt/apt.conf.d/20auto-upgrades` | lab01 | automatyczne aktualizacje |
| `/etc/nginx/nginx.conf` | lab01 | `server_tokens off` |

Konfiguracja klienta (`~/.ssh/config` na hoście):
```
Host lab01
    HostName 127.0.0.1
    Port 2222
    User mbaron
    IdentityFile ~/.ssh/id_ed25519
```

Firewall:
```
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw enable
```

## Weryfikacja

### SSH
Uprawnienia katalogu i pliku z kluczami (700 i 600, inaczej SSH zignoruje klucz):
```
$ ls -la ~/.ssh
drwx------ 2 mbaron mbaron 4096 Oct 15 16:45 .
-rw------- 1 mbaron mbaron   97 Nov  2 19:33 authorized_keys
```

Konfiguracja SSH przed zmianą i po zmianie:
```
$ sudo sshd -T | grep -Ei 'passwordauthentication|permitrootlogin'
permitrootlogin prohibit-password
passwordauthentication yes

$ sudo sshd -T | grep -Ei 'passwordauthentication|permitrootlogin|kbdinteractive'
permitrootlogin no
passwordauthentication no
kbdinteractiveauthentication no
```

Próba wymuszenia logowania hasłem kończy się odmową:
```
$ ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password lab01
mbaron@127.0.0.1: Permission denied (publickey).
```

Zmiany w SSH testowałem z otwartą drugą sesją, żeby w razie błędu nie stracić dostępu.

### Firewall
```
$ sudo ufw status verbose
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere                   # SSH
80/tcp                     ALLOW IN    Anywhere                   # HTTP
22/tcp (v6)                ALLOW IN    Anywhere (v6)              # SSH
80/tcp (v6)                ALLOW IN    Anywhere (v6)              # HTTP
```

### fail2ban
Test: 6 prób logowania z hosta jako nieistniejący użytkownik:
```
ssh -p 2222 -o PubkeyAuthentication=no test@127.0.0.1
```
Efekt: adres 10.0.2.2 (brama NAT VirtualBoxa, z której przychodzi cały ruch z hosta) został zablokowany na porcie SSH. Strona WWW działała dalej, bo blokada dotyczy tylko SSH. Odblokowanie z konsoli VirtualBoxa:
```
sudo fail2ban-client set sshd unbanip 10.0.2.2
```

### Automatyczne aktualizacje
```
$ cat /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";

$ systemctl list-timers 'apt-daily*' --no-pager
UNIT                    ACTIVATES
apt-daily-upgrade.timer apt-daily-upgrade.service
apt-daily.timer         apt-daily.service
```

### Wersja Nginx
Przed zmianą nagłówek zdradzał wersję: `Server: nginx/1.28.3 (Ubuntu)`. Po zmianie:
```
$ curl -I http://localhost
HTTP/1.1 200 OK
Server: nginx
```

## Problemy i rozwiązania
- **Problem:** mimo planu logowania tylko kluczem serwer akceptował hasła.
  **Przyczyna:** instalator Ubuntu utworzył plik `/etc/ssh/sshd_config.d/50-cloud-init.conf` z `PasswordAuthentication yes`. Serwer SSH bierze pierwszą napotkaną wartość ustawienia, a pliki z `sshd_config.d` czyta alfabetycznie.
  **Rozwiązanie:** własne ustawienia w pliku `01-hardening.conf`, który jest czytany przed `50-cloud-init.conf`. Poprawność sprawdzona przez `sshd -T`.

- **Problem:** `fail2ban-client status sshd` zwracał błąd `Failed to access socket path ... Is fail2ban running?`.
  **Przyczyna:** polecenie uruchamiało się ułamek sekundy po `systemctl restart fail2ban`, zanim usługa zdążyła wystartować.
  **Rozwiązanie:** diagnoza przez `systemctl status fail2ban` i `journalctl -u fail2ban` pokazała, że usługa działa poprawnie. Status sprawdzony chwilę później zadziałał.

- **Problem:** test fail2ban dawał `Connection refused` zamiast odmowy logowania.
  **Przyczyna:** polecenia zostały wpisane na serwerze zamiast na hoście. Przekierowanie portu 2222 istnieje tylko w VirtualBoxie na hoście.
  **Rozwiązanie:** powtórzenie testu z PowerShella na Windowsie.

## Czego się nauczyłem
- Logowanie kluczem jest bezpieczniejsze niż hasłem: klucza nie da się zgadnąć, a klucz prywatny nigdy nie opuszcza mojego komputera. Serwer zna tylko klucz publiczny.
- Zmian w konfiguracji SSH nie robi się bez zabezpieczenia: najpierw test składni (`sshd -t`), potem restart przy otwartej drugiej sesji.
- Własne ustawienia trzyma się w osobnych plikach (`sshd_config.d`, `jail.local`), a nie w plikach głównych, bo aktualizacje pakietów mogłyby je nadpisać.
- Firewall działa według zasady najmniejszych uprawnień: blokuję wszystko przychodzące i otwieram tylko potrzebne porty. Przed włączeniem trzeba dopuścić SSH.
- fail2ban czyta logi i blokuje adresy po kilku nieudanych próbach. W labie cały ruch przychodzi z jednego adresu NAT, więc blokada dotyka mnie samego.
- Komunikat o błędzie nie zawsze oznacza awarię. Najpierw sprawdzam `systemctl status` i logi usługi.