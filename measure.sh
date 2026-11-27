sel=$1
cd /home/jan/src/Landin-r22-15
landin_agent_env=$(./scripts/agent_env.sh); . "$landin_agent_env"
R=compiler/ada/build/$LANDIN_BUILD_TAG/debug/bin/refine
sc=200; [ $((sel%50)) = 15 ] && sc=20
sed "s/SEL/$sel/;s/SCALE/$sc.0/" /tmp/r2215/dblat1/scratch.ldn > /tmp/r2215/dblat1/m$sel.ldn
$R run --root . /tmp/r2215/dblat1/m$sel.ldn >/dev/null 2>&1; echo "$sel $? $sc"
