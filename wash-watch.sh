#!/bin/sh

bname=$(basename $0)
service=wash-watch
file=/var/tmp/wash-watch.alive

run_test ()
{
    local err=0
    echo -n "Checking wash-watch... "

    systemctl is-active --quiet ${service}
    
    if [ $? -eq 0 ]; then
        alive=$(find ${file} -cmin +5 2>/dev/null)
        
        if [ -f ${file} -a -z ${alive} ]; then
            echo "appears alive."
        else
            err=1
            echo "appears dead."
        fi
    else
        echo "not running."
    fi

    return ${err}
}


run_repair ()
{
    local param="$1"
    local err=0

    if [ -z "${param}" ] ; then
        echo "Missing error code (parameter) for repair"
        return 23
    fi

    echo "Restarting ${service}..."

    systemctl restart ${service}
    
    return ${err}
}


err=0

case "$1" in
    test)
        run_test
        err=$?
        ;;

    repair)
        run_repair "$2"
        err=$?
        ;;

    *)
        echo "Usage: ${bname} {test|repair errcode}"
        err=23
esac

exit ${err}
