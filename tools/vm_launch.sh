#!/usr/bin/env bash
# Drive the course VM from a laptop whose connection may drop at any moment.
#
#   ./tools/vm_launch.sh start     # sync repo to the VM and start the suite detached
#   ./tools/vm_launch.sh status    # is it still running? how far has it got?
#   ./tools/vm_launch.sh tail      # follow the log (Ctrl-C is safe, job keeps going)
#   ./tools/vm_launch.sh fetch     # copy results/ back to this machine
#   ./tools/vm_launch.sh stop      # kill the run
#
# The remote job is started under tmux (or setsid+nohup as a fallback), so it is
# detached from the SSH session: dropping the link, closing the laptop, or losing
# signal on a train does not kill it. Reconnect later and `status`/`tail`.
#
# Configure the hop with env vars (or edit the defaults):
#   VM_SSH   ssh target for the VM itself, e.g. "hwsw-vm" or "ubuntu@127.0.0.1 -p 2222"
#   VM_DIR   path of the repo checkout on the VM
set -uo pipefail

VM_SSH="${VM_SSH:-hwsw-vm}"
VM_DIR="${VM_DIR:-\$HOME/hwsw-project}"
SESSION=hwswbench
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ServerAlive* makes a half-open link fail fast instead of hanging forever; the
# remote job is unaffected either way because it is detached.
SSH=(ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -o ConnectTimeout=20)

vm() { "${SSH[@]}" $VM_SSH "$@"; }

case "${1:-status}" in

start)
    echo "==> syncing repo to $VM_SSH:$VM_DIR"
    # Push the working tree as it stands (including uncommitted edits) so the VM
    # measures exactly what is on this machine. Excludes build/junk only.
    rsync -az --delete \
        --exclude '.git' --exclude '__pycache__' --exclude 'target' \
        --exclude 'results/*.perf.data' --exclude '.venv' \
        -e "${SSH[*]}" "$ROOT/" "$VM_SSH:$VM_DIR/" || {
            echo "rsync failed — is VM_SSH=$VM_SSH reachable?" >&2; exit 1; }

    vm "chmod +x $VM_DIR/script_*.sh $VM_DIR/tools/vm_run_all.sh"

    echo "==> launching detached run"
    # tmux is preferred (reattachable); setsid+nohup is the portable fallback.
    vm "cd $VM_DIR && \
        if command -v tmux >/dev/null 2>&1; then \
            tmux kill-session -t $SESSION 2>/dev/null; \
            tmux new-session -d -s $SESSION './tools/vm_run_all.sh 2>&1 | tee vm_run.log'; \
            echo 'launched under tmux session $SESSION'; \
        else \
            rm -f vm_run.log; \
            setsid nohup ./tools/vm_run_all.sh > vm_run.log 2>&1 < /dev/null & \
            echo \"launched detached, pid \$!\"; \
        fi"
    echo "==> started. Safe to disconnect. Check with: $0 status"
    ;;

status)
    vm "cd $VM_DIR 2>/dev/null || { echo 'repo not on VM yet'; exit 1; }; \
        if [ -f results/.RUN_DONE ]; then echo \"RUN COMPLETE at \$(cat results/.RUN_DONE)\"; \
        elif tmux has-session -t $SESSION 2>/dev/null || pgrep -f vm_run_all.sh >/dev/null; then \
            echo 'RUNNING'; else echo 'NOT RUNNING (and not finished — may have died)'; fi; \
        echo '--- stages completed ---'; ls results/.stamps/ 2>/dev/null || echo none; \
        echo '--- last 15 log lines ---'; tail -15 vm_run.log 2>/dev/null || echo 'no log yet'"
    ;;

tail)
    echo "(Ctrl-C detaches; the remote job keeps running)"
    vm "cd $VM_DIR && tail -f vm_run.log"
    ;;

fetch)
    echo "==> copying results back"
    rsync -az -e "${SSH[*]}" "$VM_SSH:$VM_DIR/results/" "$ROOT/results/" \
        && echo "==> results/ updated" || echo "fetch failed" >&2
    ;;

stop)
    vm "tmux kill-session -t $SESSION 2>/dev/null; pkill -f vm_run_all.sh; echo stopped"
    ;;

*)
    echo "usage: $0 start|status|tail|fetch|stop"; exit 1 ;;
esac
