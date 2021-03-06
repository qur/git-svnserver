
from GitSvnServer import parse
from GitSvnServer import generate as gen
from GitSvnServer.cmd_base import *

class Log(SimpleCommand):
    _cmd = 'log'

    @need_repo_lock
    def do_cmd(self):
        repos = self.link.repos
        args = self.args
        url = self.link.url
        start_rev = None
        end_rev = None

        target_paths = [parse.string(x) for x in args.pop(0)]

        arg = args.pop(0)
        if len(arg) > 0:
            start_rev = int(arg[0])
            if start_rev == 0:
                start_rev = 1

        arg = args.pop(0)
        if len(arg) > 0:
            end_rev = int(arg[0])
            if end_rev == 0:
                end_rev = 1

        send_changed_paths = parse.bool(args.pop(0))

        strict_node = parse.bool(args.pop(0))

        limit = 0
        if len(args) > 0:
            limit = int(args.pop(0))

        include_merged_revisions = False
        if len(args) > 0:
            include_merged_revisions = parse.bool(args.pop(0))

        # all-revprops | revprops

        # ( revprop:string ... )

        for changes, rev, author, date, msg, has_children, revprops in repos.log(url, target_paths, start_rev, end_rev, limit):
            changed_paths = []
            if send_changed_paths:
                for path, data in sorted(changes.items()):
                    change, cp, cr, kind, tmod, pmod = data
                    copy = gen.list()
                    if cp is not None and cr is not None:
                        copy = gen.list(gen.string(cp), cr)
                    ct = gen.list(gen.string(kind), gen.bool(tmod),
                                  gen.bool(pmod))
                    changed_paths.append(gen.list(gen.string(path),
                                         change, copy, ct))
            log_entry = gen.list(gen.list(*changed_paths),
                                 rev,
                                 gen.list(gen.string(author)),
                                 gen.list(gen.string(date)),
                                 gen.list(gen.string(msg)))
            self.link.send_msg(log_entry)

        self.link.send_msg('done')

        self.link.send_msg(gen.success())

