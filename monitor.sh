echo
echo "NETSTAT INFO"
netstat -anp 2>/dev/null | grep ESTABLISHED | awk 'BEGIN { countsvc=0; countrouter=0 }; {if ($4 ~ /:9[0-9]9[0-9]/) countsvc++; else if ($4 ~ /:8[0-9]8[0-9]?/) countrouter++}; END {print "Connections to service:", countsvc; print "Connections to router :", countrouter}'
netstat -anp 2>/dev/null | grep CLOSE_WAIT | awk 'BEGIN { countsvc=0; countrouter=0 }; {if ($4 ~ /:9[0-9]9[0-9]/) countsvc++; else if ($4 ~ /:8[0-9]8[0-9]?/) countrouter++}; END {print "Close Wait to service :", countsvc; print "Close wait to router  :", countrouter}'

echo
echo "SKSTAT"
echo "skstat -c: $(skstat -c | wc -l)"
echo "skstat -l: $(skstat -l | wc -l)"
