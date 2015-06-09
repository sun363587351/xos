import os
import socket
import sys
import base64
from django.db.models import F, Q
from xos.config import Config
from observer.syncstep import SyncStep
from observer.ansible import run_template_ssh
from core.models import Service
from cord.models import VCPEService, VCPETenant, VOLTTenant
from hpc.models import HpcService, CDNPrefix
from util.logger import Logger, logging

# hpclibrary will be in steps/..
parentdir = os.path.join(os.path.dirname(__file__),"..")
sys.path.insert(0,parentdir)

from broadbandshield import BBS

logger = Logger(level=logging.INFO)

class SyncVCPETenant(SyncStep):
    provides=[VCPETenant]
    observes=VCPETenant
    requested_interval=0
    template_name = "sync_vcpetenant.yaml"
    service_key_name = "/opt/xos/observers/vcpe/vcpe_private_key"

    def __init__(self, **args):
        SyncStep.__init__(self, **args)

    def defer_sync(self, o, reason):
        logger.info("defer object %s due to %s" % (str(o), reason))
        raise Exception("defer object %s due to %s" % (str(o), reason))

    def fetch_pending(self, deleted):
        if (not deleted):
            objs = VCPETenant.get_tenant_objects().filter(Q(enacted__lt=F('updated')) | Q(enacted=None),Q(lazy_blocked=False))
        else:
            objs = VCPETenant.get_deleted_tenant_objects()

        return objs

    def get_extra_attributes(self, o):
        # This is a place to include extra attributes that aren't part of the
        # object itself. In our case, it's handy to know the VLAN IDs when
        # configuring the VCPE.

        dnsdemux_ip = "none"
        for service in HpcService.objects.all():
            for slice in service.slices.all():
                if "dnsdemux" in slice.name:
                    for sliver in slice.slivers.all():
                        # Connect to a dnsdemux that's on the hpc_client network
                        # if one is available.
                        for ns in sliver.networkslivers.all():
                            if ns.ip and ns.network.labels and ("hpc_client" in ns.network.labels):
                                dnsdemux_ip = ns.ip
                        if dnsdemux_ip=="none":
                            try:
                                dnsdemux_ip = socket.gethostbyname(sliver.node.name)
                            except:
                                pass

        cdn_prefixes = []
        for prefix in CDNPrefix.objects.all():
            cdn_prefixes.append(prefix.prefix)

        volts = [x for x in VOLTTenant.get_tenant_objects() if (x.vcpe is not None) and (x.vcpe.id==o.id)]
        vlan_ids = [x.vlan_id for x in volts]
        return {"vlan_ids": vlan_ids,
                "dnsdemux_ip": dnsdemux_ip,
                "cdn_prefixes": cdn_prefixes}

    def get_sliver(self, o):
        # We need to know what slivers is associated with the object.
        # For vCPE this is easy, as VCPETenant has a sliver field.

        return o.sliver

    def sync_record(self, o):
        logger.info("sync'ing VCPETenant %s" % str(o))

        sliver = self.get_sliver(o)
        if not sliver:
            self.defer_sync(o, "waiting on sliver")
            return

        service = o.sliver.slice.service
        if not service:
            # Ansible uses the service's keypair in order to SSH into the
            # instance. It would be bad if the slice had no service.

            raise Exception("Slice %s is not associated with a service" % sliver.slice.name)

        if not os.path.exists(self.service_key_name):
            raise Exception("Service key %s does not exist" % self.service_key_name)

        service_key = file(self.service_key_name).read()

        fields = { "sliver_name": sliver.name,
                   "hostname": sliver.node.name,
                   "instance_id": sliver.instance_id,
                   "private_key": service_key,
                   "ansible_tag": "vcpe_tenant_" + str(o.id)
                 }

        if hasattr(o, "sync_attributes"):
            for attribute_name in o.sync_attributes:
                 fields[attribute_name] = getattr(o, attribute_name)

        fields.update(self.get_extra_attributes(o))
        run_template_ssh(self.template_name, fields)

        if o.url_filter_enable:
            if (str(o.service_specific_id) != "0"):
                # XXX FIXME
                # Also fix the spot in cord/models.py
                logger.info("skipping sync of URL filter for SSID %s" % str(o.service_specific_id))
            else:
                bbs = BBS(o.bbs_account, "123")
                bbs.sync(o.url_filter_level, o.users)

        o.save()

    def delete_record(self, m):
        pass

