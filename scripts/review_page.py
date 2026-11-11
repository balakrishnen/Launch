"""Inline the VITE_REVIEW bundle into review/page.html. The bundle uses import.meta (lazy three.js chunk) so it must be a module script."""
import glob, sys
out, page = sys.argv[1], sys.argv[2]
js = open(glob.glob(out + '/assets/index-*.js')[0]).read().replace('</script>', '<\\/script>').replace('�', '')
css = open(glob.glob(out + '/assets/*.css')[0]).read()
pre = open(page).read().split('<div id="root">')[0]
open(page, 'w').write(pre + '<div id="root"></div>\n<style>' + css + '</style>\n<script type="module">' + js + '</script>\n')
print(page, 'ok; publish assets/three.module-*.js from', out, 'alongside')
