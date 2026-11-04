# Uptime Platform

Platforma monitorująca dostępność stron WWW, budowana etapami jak w środowisku produkcyjnym:
od pojedynczego serwera Linux, przez kontenery i CI/CD, po chmurę, Kubernetes i monitoring.

## Status

| Etap | Zakres | Stan |
| --- | --- | --- |
| 1 | Linux, Nginx, Python, PostgreSQL, backup | w trakcie |
| 2 | Docker, CI/CD, Ansible | planowany |
| 3 | Chmura, Terraform | planowany |
| 4 | Kubernetes, monitoring, DevSecOps | planowany |

## Moduły

### Etap 1: Fundamenty
- [x] [Moduł 1: Serwer WWW](docs/moduly/modul-01-serwer-www.md)
- [x] [Moduł 2: Bezpieczny serwer](docs/moduly/modul-02-bezpieczny-serwer.md)
- [x] [Moduł 3: Dysk](docs/moduly/modul-03-dysk.md)
- [ ] Moduł 4: Aplikacja v1
- [ ] Moduł 5: Baza danych
- [ ] Moduł 6: Backup
- [ ] Moduł 7: Dokumentacja etapu 1

## Środowisko

- Serwer `lab01`: Ubuntu Server LTS w VirtualBox
- Dysk zarządzany przez LVM: system w `/`, dane aplikacji na osobnym wolumenie w `/srv`
- Dostęp z hosta przez przekierowanie portów: SSH (2222) i HTTP (8080)
- Logowanie wyłącznie kluczem SSH, firewall ufw, fail2ban, automatyczne aktualizacje bezpieczeństwa

## Struktura repozytorium

```
config/        pliki konfiguracyjne serwera
docs/moduly/   opis każdego modułu: kroki, konfiguracja, weryfikacja, problemy
docs/img/      zrzuty ekranu do dokumentacji
```

## Autor

Miłosz Baron