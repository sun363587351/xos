def get_controller (self):
    return self.node.site_deployment.controller

def tologdict(self):
    d=super(Instance,self).tologdict()
    try:
        d['slice_name']=self.slice.name
        d['controller_name']=self.get_controller().name
    except:
        pass
    return d

def __xos_save_base(self, *args, **kwds):
    if not self.name:
        self.name = self.slice.name
    if not self.creator and hasattr(self, 'caller'):
        self.creator = self.caller

def all_ips(self):
    ips={}
    for ns in self.ports.all():
       if ns.ip:
           ips[ns.network.name] = ns.ip
    return ips

def all_ips_string(self):
    result = []
    ips = self.all_ips()
    for key in sorted(ips.keys()):
        #result.append("%s = %s" % (key, ips[key]))
        result.append(ips[key])
    return ", ".join(result)
all_ips_string.short_description = "addresses"

def get_public_ip(self):
    for ns in self.ports.all():
        if (ns.ip) and (ns.network.template.visibility=="public") and (ns.network.template.translation=="none"):
            return ns.ip
    return None

# return an address on nat-net
def get_network_ip(self, pattern):
    for ns in self.ports.all():
        if pattern in ns.network.name.lower():
            return ns.ip
    return None

# return an address that the synchronizer can use to SSH to the instance
def get_ssh_ip(self):
    # first look specifically for a management_local network
    for ns in self.ports.all():
        if ns.network.template and ns.network.template.vtn_kind=="MANAGEMENT_LOCAL":
            return ns.ip

    # for compatibility, now look for any management network
    management=self.get_network_ip("management")
    if management:
        return management

    # if all else fails, look for nat-net (for OpenCloud?)
    return self.get_network_ip("nat")

def get_ssh_command(self):
    if (not self.instance_id) or (not self.node) or (not self.instance_name):
        return None
    else:
        return 'ssh -o "ProxyCommand ssh -q %s@%s" ubuntu@%s' % (self.instance_id, self.node.name, self.instance_name)

def get_public_keys(self):
    from core.models.sliceprivilege import Privilege
    slice_privileges = Privilege.objects.filter(object_id=self.slice.id, object_type='Slice', accessor_type='User')
    slice_users = [User.objects.get(pk = priv.accessor_id) for priv in slice_privileges]
    pubkeys = set([u.public_key for u in slice_users if u.public_key])

    if self.creator.public_key:
        pubkeys.add(self.creator.public_key)

    if self.slice.creator.public_key:
        pubkeys.add(self.slice.creator.public_key)

    if self.slice.service and self.slice.service.public_key:
        pubkeys.add(self.slice.service.public_key)

    return pubkeys
