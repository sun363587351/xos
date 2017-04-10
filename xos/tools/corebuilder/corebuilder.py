""" CoreBuilder

    Read XOS Tosca Onboarding Recipes and generate a BUILD directory.

    Arguments:
        A list of onboarding recipes. Except this list to originate from
        platform-install's service inventory in the profile manifest.

    Output:
        /opt/xos_corebuilder/BUILD, populated with files from services

    Example:
        # for testing, run from inside a UI container
        python ./corebuilder.py \
            /opt/xos_services/olt/xos/volt-onboard.yaml \
            /opt/xos_services/vtn/xos/vtn-onboard.yaml \
            /opt/xos_services/openstack/xos/openstack-onboard.yaml \
            /opt/xos_services/onos-service/xos/onos-onboard.yaml \
            /opt/xos_services/vrouter/xos/vrouter-onboard.yaml \
            /opt/xos_services/vsg/xos/vsg-onboard.yaml \
            /opt/xos_services/vtr/xos/vtr-onboard.yaml \
            /opt/xos_services/fabric/xos/fabric-onboard.yaml \
            /opt/xos_services/exampleservice/xos/exampleservice-onboard.yaml \
            /opt/xos_services/monitoring/xos/monitoring-onboard.yaml \
            /opt/xos_libraries/ng-xos-lib/ng-xos-lib-onboard.yaml

        # (hypothetical) run from build container
        python ./corebuilder.py \
            /opt/cord/onos-apps/apps/olt/xos/volt-onboard.yaml \
            /opt/cord/onos-apps/apps/vtn/xos/vtn-onboard.yaml \
            /opt/cord/orchestration/xos_services/openstack/xos/openstack-onboard.yaml \
            /opt/cord/orchestration/xos_services/onos-service/xos/onos-onboard.yaml \
            /opt/cord/orchestration/xos_services/vrouter/xos/vrouter-onboard.yaml \
            /opt/cord/orchestration/xos_services/vsg/xos/vsg-onboard.yaml \
            /opt/cord/orchestration/xos_services/vtr/xos/vtr-onboard.yaml \
            /opt/cord/orchestration/xos_services/fabric/xos/fabric-onboard.yaml \
            /opt/cord/orchestration/xos_services/exampleservice/xos/exampleservice-onboard.yaml \
            /opt/cord/orchestration/xos_services/monitoring/xos/monitoring-onboard.yaml \
            /opt/cord/orchestration/xos_libraries/ng-xos-lib/ng-xos-lib-onboard.yaml
"""

import os
import pdb
import shutil
import sys
import tempfile
import traceback
import urlparse

from toscaparser.tosca_template import ToscaTemplate

BUILD_DIR = "/opt/xos_corebuilder/BUILD"

def makedirs_if_noexist(pathname):
    if not os.path.exists(pathname):
        os.makedirs(pathname)

class XOSCoreBuilder(object):
    def __init__(self, recipe_list, parent_dir=None):
        # TOSCA will look for imports using a relative path from where the
        # template file is located, so we have to put the template file
        # in a specific place.
        if not parent_dir:
            parent_dir = os.getcwd()

        self.parent_dir = parent_dir

        # list of resources in the form (src_fn, dest_fn)
        self.resources = []

        # list of __init__.py files that should be ensured
        self.inits = []

        self.app_names = []

        for recipe in recipe_list:
            tosca_yaml = open(recipe).read()
            self.execute_recipe(tosca_yaml)

    def get_property_default(self, nodetemplate, name, default=None):
        props = nodetemplate.get_properties()
        if props and name in props.keys():
            return props[name].value
        return default

    def get_dest_dir(self, kind, service_name):
        xos_base = "opt/xos"
        base_dirs = {"models": "%s/services/%s/" % (xos_base, service_name),
                     "xproto": "%s/services/%s/xproto/" % (xos_base, service_name),
                     "admin": "%s/services/%s/" % (xos_base, service_name),
                     "admin_template": "%s/services/%s/templates/" % (xos_base, service_name),
                     "django_library": "%s/services/%s/" % (xos_base, service_name),
                     "synchronizer": "%s/synchronizers/%s/" % (xos_base, service_name),
                     "tosca_custom_types": "%s/tosca/custom_types/" % (xos_base),
                     "tosca_resource": "%s/tosca/resources/" % (xos_base),
                     "rest_service": "%s/api/service/" % (xos_base),
                     "rest_tenant": "%s/api/tenant/" % (xos_base),
                     "private_key": "%s/services/%s/keys/" % (xos_base, service_name),
                     "public_key": "%s/services/%s/keys/" % (xos_base, service_name),
                     "vendor_js": "%s/core/xoslib/static/vendor/" % (xos_base)}
        dest_dir = base_dirs[kind]

        return dest_dir

    def fixup_path(self, fn):
        """ This is to maintain compatibility with the legacy Onboarding
            synchronizer and recipes, which has some oddly-named directories
        """

#        if fn.startswith("/opt/xos/key_import"):
#            fn = "/opt/cord_profile/key_import" + fn[19:]

        fixups = ( ("/opt/xos_services/olt/", "/opt/cord/onos-apps/apps/olt/"),
                   ("/opt/xos_services/vtn/", "/opt/cord/onos-apps/apps/vtn/"),
                   ("/opt/xos_services/", "/opt/cord/orchestration/xos_services/"),
                   ("/opt/xos_libraries/", "/opt/cord/orchestration/xos_libraries/") )

        for (pattern, replace) in fixups:
            if fn.startswith(pattern):
                fn = replace + fn[len(pattern):]

        return fn

    def execute_recipe(self, tosca_yaml):
        tmp_pathname = None
        try:
            (tmp_handle, tmp_pathname) = tempfile.mkstemp(dir=self.parent_dir, suffix=".yaml")
            os.write(tmp_handle, tosca_yaml)
            os.close(tmp_handle)

            template = ToscaTemplate(tmp_pathname)
        except:
            traceback.print_exc()
            raise
        finally:
            if tmp_pathname:
                os.remove(tmp_pathname)

        # Only one model (ServiceController aka Library), so no need to sort
        # dependencies...

        for nodetemplate in template.nodetemplates:
            self.execute_nodetemplate(nodetemplate)

    def execute_nodetemplate(self, nodetemplate):
        if nodetemplate.type == "tosca.nodes.ServiceController":
            self.execute_servicecontroller(nodetemplate)
        elif nodetemplate.type == "tosca.nodes.Library":
            # Library works just like ServiceController
            self.execute_servicecontroller(nodetemplate)
        else:
            raise Exception("Nodetemplate %s's type %s is not a known resource" % (nodetemplate.name, nodetemplate.type))

    def execute_servicecontroller(self, nodetemplate):
        service_name = nodetemplate.name
        if "#" in service_name:
            service_name = service_name.split("#")[1]

        base = self.get_property_default(nodetemplate, "base_url", None)

        copyin_resources = ("xproto", "models", "admin", "admin_template", "django_library", "tosca_custom_types", "tosca_resource",
                            "rest_service", "rest_tenant", "private_key", "public_key", "vendor_js")

        for k in copyin_resources:
            v = self.get_property_default(nodetemplate, k, None)
            if not v:
                continue

            # Private keys should not be installed to core, only synchronizers
            if (k=="private_key"):
                continue

            # Public keys should be volume mounted in /opt/cord_profile
            if (k=="public_key"):
                continue

            # If the ServiceController has models, then add it to the list of
            # django apps.
            if (k=="models"):
                self.app_names.append(service_name)

            # filenames can be comma-separated
            for src_fn in v.split(","):
                src_fn = src_fn.strip()

                # parse the "subdirectory:name" syntax
                subdirectory = ""
                if (" " in src_fn):
                    parts=src_fn.split()
                    for part in parts[:-1]:
                       if ":" in part:
                           (lhs, rhs) = part.split(":", 1)
                           if lhs=="subdirectory":
                               subdirectory=rhs
                           else:
                               raise Exception("Malformed value %s" % value)
                       else:
                           raise Exception("Malformed value %s" % value)
                    src_fn = parts[-1]

                # apply base_url to src_fn
                if base:
                    src_fn = urlparse.urljoin(base, src_fn)

                # ensure that it's a file:// url
                if not src_fn.startswith("file://"):
                    raise Exception("%s does not start with file://" % src_fn)
                src_fn = src_fn[7:]

                src_fn = self.fixup_path(src_fn)

                if not os.path.exists(src_fn):
                    raise Exception("%s does not exist" % src_fn)

                dest_dir = self.get_dest_dir(k, service_name)
                dest_fn = os.path.join(dest_dir, subdirectory, os.path.basename(src_fn))

                self.resources.append( (k, src_fn, dest_fn) )

                # add __init__.py files anywhere that we created a new
                # directory.
                if k in ["admin", "models", "rest_service", "rest_tenant"]:
                    if dest_dir not in self.inits:
                        self.inits.append(dest_dir)

                    if subdirectory:
                        dir = dest_dir
                        for part in subdirectory.split("/"):
                            dir = os.path.join(dir, part)
                            if dir not in self.inits:
                                self.inits.append(dir)

    def build(self):
        # Destroy anything in the old build directory
        if os.path.exists(BUILD_DIR):
            for dir in os.listdir(BUILD_DIR):
                shutil.rmtree(os.path.join(BUILD_DIR, dir))

        # Copy all of the resources into the build directory
        for (kind, src_fn, dest_fn) in self.resources:
#            if (kind == "xproto"):
#               build_dest_dir = os.path.join(BUILD_DIR, os.path.dirname(dest_fn))

                # TODO: If we wanted to statically compile xproto files, then
                #   this is where we could do it. src_fn would be the name of
                #   the xproto file, and build_dest_dir would be the place
                #   to store the generated files.

            build_dest_fn = os.path.join(BUILD_DIR, dest_fn)
            makedirs_if_noexist(os.path.dirname(build_dest_fn))
            shutil.copyfile(src_fn, build_dest_fn)

        # Create the __init__.py files
        for fn in self.inits:
            build_dest_fn = os.path.join(BUILD_DIR, fn, "__init__.py")
            makedirs_if_noexist(os.path.dirname(build_dest_fn))
            file(build_dest_fn, "w").write("")

        # Generate the migration list
        mig_list_fn = os.path.join(BUILD_DIR, "opt/xos/xos", "xosbuilder_migration_list")
        makedirs_if_noexist(os.path.dirname(mig_list_fn))
        file(mig_list_fn, "w").write("\n".join(self.app_names)+"\n")

        # Generate the app list
        app_list_fn = os.path.join(BUILD_DIR, "opt/xos/xos", "xosbuilder_app_list")
        makedirs_if_noexist(os.path.dirname(app_list_fn))
        file(app_list_fn, "w").write("\n".join(["services.%s" % x for x in self.app_names])+"\n")

def main():
   if len(sys.argv)<=1:
       print >> sys.stderr, "Syntax: corebuilder.py [recipe1, recipe2, ...]"

   builder = XOSCoreBuilder(sys.argv[1:])
   builder.build()

if __name__ == "__main__":
    main()








