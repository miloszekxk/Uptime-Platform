# Moduł 3: Dysk

## Cel
Wykorzystać wolne miejsce w LVM: powiększyć partycję systemową i utworzyć osobny wolumen na dane aplikacji, montowany automatycznie przy starcie.

## Plan podziału miejsca
W grupie `ubuntu-vg` instalator zostawił 11,5 GB wolnego miejsca. Podział:
- 5 GB dla partycji systemowej `/`,
- 4 GB na nowy wolumen z danymi aplikacji w `/srv`,
- około 2,5 GB rezerwy w grupie (powiększyć wolumen łatwo, zmniejszyć trudno).

Osobny wolumen na dane chroni system: jeśli aplikacja zapełni swój dysk, `/` dalej ma wolne miejsce. Dane można też osobno powiększać i archiwizować.

## Wykonane kroki
1. Przegląd dysków i warstw LVM: `lsblk`, `df -h`, `pvs`, `vgs`, `lvs`.
2. Powiększenie partycji systemowej o 5 GB razem z systemem plików, bez restartu:
   `sudo lvextend -r -L +5G /dev/ubuntu-vg/ubuntu-lv`
3. Utworzenie wolumenu na dane i systemu plików ext4:
   `sudo lvcreate -L 4G -n data-lv ubuntu-vg`
   `sudo mkfs.ext4 -L appdata /dev/ubuntu-vg/data-lv`
4. Kopia zapasowa `/etc/fstab` i dodanie wpisu montującego wolumen w `/srv` po UUID.
5. Test wpisu bez restartu: `umount`, `findmnt --verify`, `mount -a`.
6. Restart serwera i sprawdzenie dysków oraz usług.

## Konfiguracja
Wpis dodany do `/etc/fstab`:
```
UUID=22ed8c6b-6347-4265-86b7-871a64063df7  /srv  ext4  defaults  0  2
```

| Pole | Wartość | Znaczenie |
| --- | --- | --- |
| urządzenie | `UUID=...` | system plików wskazany po UUID, który nie zmienia się po dodaniu dysków |
| punkt montowania | `/srv` | katalog na dane usług |
| typ | `ext4` | system plików |
| opcje | `defaults` | standardowe montowanie |
| dump | `0` | nieużywane |
| fsck | `2` | sprawdzanie przy starcie po partycji `/` |

Przed edycją zrobiłem kopię: `/etc/fstab.bak`. Błąd w `fstab` może zablokować uruchomienie systemu.

## Weryfikacja

### Stan przed zmianami
```
$ lsblk
sda                         8:0    0   25G  0 disk
├─sda1                      8:1    0    1M  0 part
├─sda2                      8:2    0    2G  0 part /boot
└─sda3                      8:3    0   23G  0 part
  └─ubuntu--vg-ubuntu--lv 252:0    0 11.5G  0 lvm  /

$ sudo vgs
  VG        #PV #LV #SN Attr   VSize   VFree
  ubuntu-vg   1   1   0 wz--n- <23.00g 11.50g

$ df -h /
/dev/mapper/ubuntu--vg-ubuntu--lv   12G  5.2G  5.5G  49% /
```

### Powiększenie partycji systemowej
```
$ sudo lvextend -r -L +5G /dev/ubuntu-vg/ubuntu-lv
  Size of logical volume ubuntu-vg/ubuntu-lv changed from <11.50 GiB (2943 extents) to <16.50 GiB (4223 extents).
Filesystem at /dev/ubuntu-vg/ubuntu-lv is mounted on /; on-line resizing required
  Logical volume ubuntu-vg/ubuntu-lv successfully resized.

$ df -h /
/dev/mapper/ubuntu--vg-ubuntu--lv   17G  5.2G   11G  34% /
```
Opcja `-r` powiększa od razu system plików (`resize2fs`). Bez niej wolumen byłby większy, ale `df` pokazywałby stary rozmiar. Ext4 da się powiększać na zamontowanym systemie, bez przerwy w działaniu.

### Nowy wolumen na dane
```
$ sudo lvcreate -L 4G -n data-lv ubuntu-vg
  Logical volume "data-lv" created.

$ sudo mkfs.ext4 -L appdata /dev/ubuntu-vg/data-lv
Creating filesystem with 1048576 4k blocks and 262144 inodes
Filesystem UUID: 22ed8c6b-6347-4265-86b7-871a64063df7
```

### Test wpisu w fstab
```
$ sudo findmnt --verify
   [W] non-bind mount source /swap.img is a directory or regular file
0 parse errors, 0 errors, 1 warning

$ sudo mount -a
$ df -h /srv
/dev/mapper/ubuntu--vg-data--lv  3.9G  1.1M  3.7G   1% /srv
```

### Po restarcie
```
$ df -h / /srv
/dev/mapper/ubuntu--vg-ubuntu--lv   17G  5.2G   11G  34% /
/dev/mapper/ubuntu--vg-data--lv    3.9G  1.1M  3.7G   1% /srv

$ systemctl is-active nginx ssh fail2ban ufw
active
active
active
active
```
Wolumen zamontował się sam, a wszystkie usługi z poprzednich modułów uruchomiły się automatycznie.

### Stan końcowy
```
$ lsblk /dev/sda
NAME                      MAJ:MIN RM  SIZE RO TYPE MOUNTPOINTS
sda                         8:0    0   25G  0 disk
├─sda1                      8:1    0    1M  0 part
├─sda2                      8:2    0    2G  0 part /boot
└─sda3                      8:3    0   23G  0 part
  ├─ubuntu--vg-ubuntu--lv 252:0    0 16.5G  0 lvm  /
  └─ubuntu--vg-data--lv   252:1    0    4G  0 lvm  /srv

$ sudo vgs
  VG        #PV #LV #SN Attr   VSize   VFree
  ubuntu-vg   1   2   0 wz--n- <23.00g 2.50g

$ sudo lvs
  LV        VG        Attr       LSize   Pool Origin Data%  Meta%  Move Log Cpy%Sync Convert
  data-lv   ubuntu-vg -wi-ao----   4.00g
  ubuntu-lv ubuntu-vg -wi-ao---- <16.50g
```

## Problemy i obserwacje
- **Obserwacja:** `findmnt --verify` zgłasza ostrzeżenie dla `/swap.img`.
  **Wyjaśnienie:** to wpis pliku wymiany (swap). Źródłem jest zwykły plik, a nie urządzenie, co dla pliku swap jest normalne. Ostrzeżenie nie wpływa na działanie.
- **Obserwacja:** nowy wolumen 4 GB pokazuje 3,9 GB rozmiaru i 3,7 GB dostępnego miejsca.
  **Wyjaśnienie:** część miejsca zajmują struktury systemu plików, a ext4 rezerwuje 5% dla roota, żeby system działał nawet przy zapełnionym dysku.
- **Problem:** po wklejeniu do terminala fragmentu dokumentacji Bash próbował wykonać wyniki poleceń i znaki zachęty jako polecenia.
  **Przyczyna:** w schowku był tekst z wynikami, a nie same polecenia.
  **Rozwiązanie:** do terminala wklejam tylko polecenia, które przeczytałem. Wklejenie nieznanego tekstu mogłoby wykonać coś niebezpiecznego.

## Czego się nauczyłem
- LVM dzieli miejsce na kawałki (extents, po 4 MiB), dlatego wolumeny można powiększać bez ruszania partycji.
- Powiększenie dysku to dwa kroki: wolumen (`lvextend`) i system plików na nim (`resize2fs`). Opcja `-r` robi oba naraz.
- Dane aplikacji trzyma się na osobnym wolumenie, żeby nie zapełniły systemu.
- `mkfs` kasuje wszystko na wskazanym urządzeniu, więc ścieżkę zawsze sprawdzam dwa razy.
- Wpisy w `fstab` robi się po UUID, a każdą zmianę testuje przez `findmnt --verify` i `mount -a` przed restartem. Kopia `fstab.bak` pozwala naprawić system z trybu awaryjnego.