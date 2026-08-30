#!/usr/bin/env bash
# Drive the course VM from a laptop whose connection may drop at any moment.
#
#   ./tools/vm_launch.sh start [bench...]   # sync repo to the VM, start suite detached
#   ./tools/vm_launch.sh status             # still running? how far has it got?
#   ./tools/vm_launch.sh tail               # follow the log (Ctrl-C is safe)
#   ./tools/vm_launch.sh fetch              # copy results/ back to this machine
#   ./tools/vm_launch.sh stop               # kill the run
#   ./tools/vm_launch.sh shell "cmd"        # run one command on the VM
#
# The remote job runs inside a tmux session on the VM, so it is detached from
# the SSH session: losing signal, closing the laptop, or the link dying does not
# kill it. Reconnect later and `status` / `tail`.
#
# TOPOLOGY. The VM is a QEMU guest on the Technion host, reachable only as a
# port forward on that host's loopback (127.0.0.1:12222). Our laptop key is
# authorized on the host; the host's key is authorized on the guest. Rather than
# install another key on the guest, every operation relays through the host:
#
#     laptop  --ssh-->  naranja14  --ssh -p 12222-->  guest VM
#
# File transfer is therefore two hops: laptop -> host staging dir -> guest.
set -uo pipefail

JUMP="${JUMP:-ece882-017@naranja14.cslcs.technion.ac.il}"
VM_PORT="${VM_PORT:-12222}"
VM_USER="${VM_USER:-ubuntu}"
STAGE="${STAGE:-\$HOME/hwsw-stage}"     # staging dir on the jump host
VM_DIR="${VM_DIR:-/home/ubuntu/hwsw-project}" # repo checkout on the guest (absolute: $HOME would expand on the JUMP host)
SESSION=hwswbench
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ServerAlive* makes a half-open link fail fast instead of hanging; the remote
# job is detached, so a dropped control connection costs nothing.
SSHOPTS=(-o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ConnectTimeout=25)
GUEST_SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=no -p $VM_PORT $VM_USER@127.0.0.1"

jump() { ssh "${SSHOPTS[@]}" "$JUMP" "$@"; }

# Run a script on the guest. The command crosses two shells (laptop -> jump ->
# guest), so anything quote-heavy gets mangled by the time it lands. Ship it
# base64-encoded instead: no escaping, no surprises.
guest() {
    local enc
    enc=$(printf '%s' "$1" | base64 | tr -d '\n')
    jump "$GUEST_SSH 'echo $enc | base64 -d | bash'"
}

case "${1:-status}" in

start)
    shift
    BENCHES="$*"
    echo "==> hop 1/2: laptop -> $JUMP:$STAGE"
    # tar over ssh, not rsync: Git Bash on Windows ships no rsync, and this
    # needs nothing beyond ssh+tar on either end.
    # results/ is excluded so the VM's own measurements and resume stamps are
    # never clobbered by a re-push.
    tar czf - -C "$ROOT" \
        --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
        --exclude 'target' --exclude '.venv' --exclude 'results' . \
      | jump "rm -rf \$HOME/hwsw-stage && mkdir -p \$HOME/hwsw-stage \
              && tar xzf - -C \$HOME/hwsw-stage && echo staged" || {
            echo "hop 1 failed" >&2; exit 1; }

    echo "==> hop 2/2: $JUMP -> guest:$VM_DIR"
    # 'venv' is excluded from --delete as well: pyperformance builds its run
    # venv inside the checkout, and wiping it on every push would force a full
    # dependency reinstall (and needs network) before each run.
    jump "rsync -a --delete \
            --exclude '.git' --exclude '__pycache__' --exclude 'results' \
            --exclude 'venv' \
            -e 'ssh -o BatchMode=yes -o StrictHostKeyChecking=no -p $VM_PORT' \
            \$HOME/hwsw-stage/ $VM_USER@127.0.0.1:hwsw-project/" \
        || { echo "hop 2 failed" >&2; exit 1; }

    guest "chmod +x $VM_DIR/script_*.sh $VM_DIR/tools/vm_run_all.sh"

    echo "==> launching detached run (tmux session '$SESSION')"
    guest "cd $VM_DIR && tmux kill-session -t $SESSION 2>/dev/null; \
           tmux new-session -d -s $SESSION './tools/vm_run_all.sh $BENCHES 2>&1 | tee vm_run.log'; \
           sleep 1; tmux has-session -t $SESSION && echo LAUNCHED"
    echo "==> started. Safe to disconnect now. Check with: $0 status"
    ;;

status)
    guest "
cd $VM_DIR 2>/dev/null || { echo 'repo not on VM yet'; exit 0; }
if [ -f results/.RUN_DONE ]; then
    echo \"RUN COMPLETE at \$(cat results/.RUN_DONE)\"
elif tmux has-session -t $SESSION 2>/dev/null; then
    echo RUNNING
else
    echo 'NOT RUNNING (and no completion marker - may have died)'
fi
echo '--- stages done ---'
ls results/.stamps/ 2>/dev/null | tr '\n' ' '; echo
echo '--- progress ---'
grep -E '^\[.*\] (START|OK|FAIL|SKIP)' vm_run.log 2>/dev/null | tail -12 || echo 'no log yet'
"
    ;;

tail)
    echo "(Ctrl-C detaches; the remote job keeps running)"
    guest "cd $VM_DIR && tail -f vm_run.log"
    ;;

fetch)
    echo "==> guest -> $JUMP staging"
    jump "rsync -a -e 'ssh -o BatchMode=yes -o StrictHostKeyChecking=no -p $VM_PORT' \
          $VM_USER@127.0.0.1:hwsw-project/results/ \$HOME/hwsw-results/" || {
          echo "guest->host fetch failed" >&2; exit 1; }
    echo "==> $JUMP -> laptop"
    jump "tar czf - -C \$HOME/hwsw-results ." | tar xzf - -C "$ROOT/results" \
        && echo "==> results/ updated" || { echo "host->laptop fetch failed" >&2; exit 1; }
    ;;

stop)
    guest "tmux kill-session -t $SESSION 2>/dev/null; pkill -f vm_run_all.sh; echo stopped"
    ;;

shell)
    shift
    guest "$*"
    ;;

*)
    echo "usage: $0 start [bench...]|status|tail|fetch|stop|shell <cmd>"; exit 1 ;;
esac
