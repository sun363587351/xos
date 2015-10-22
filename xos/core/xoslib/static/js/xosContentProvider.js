/* global angular */
/* eslint-disable dot-location*/

angular.module('contentProviderApp', [
  'ngResource',
  'ngRoute',
  'ngCookies',
  'ngLodash'
])
.config(function($interpolateProvider, $routeProvider, $resourceProvider) {
  $interpolateProvider.startSymbol('{$');
  $interpolateProvider.endSymbol('$}');

  // NOTE http://www.masnun.com/2013/09/18/django-rest-framework-angularjs-resource-trailing-slash-problem.html
  $resourceProvider.defaults.stripTrailingSlashes = false;

  $routeProvider
  .when('/', {
    template: '<content-provider-list></content-provider-list>',
  })
  .when('/contentProvider/:id?', {
    template: '<content-provider-detail></content-provider-detail>'
  })
  .when('/contentProvider/:id/cdn_prefix', {
    template: '<content-provider-cdn></content-provider-cdn>'
  })
  .when('/contentProvider/:id/origin_server', {
    template: '<content-provider-server></content-provider-server>'
  })
  .when('/contentProvider/:id/users', {
    template: '<content-provider-users></content-provider-users>'
  })
  .otherwise('/');
})
.config(function($httpProvider) {

  // add X-CSRFToken header for update, create, delete (!GET)
  $httpProvider.interceptors.push('SetCSRFToken');
})
.factory('SetCSRFToken', function($cookies) {
  return {
    request: function(request) {
      if(request.method !== 'GET') {
        request.headers['X-CSRFToken'] = $cookies.get('csrftoken');
      }
      return request;
    }
  };
})
.service('ContentProvider', function($resource) {
  return $resource('/hpcapi/contentproviders/:id/', {id: '@id'}, {
    'update': {method: 'PUT'}
  });
})
.service('ServiceProvider', function($resource) {
  return $resource('/hpcapi/serviceproviders/:id/', {id: '@id'});
})
.service('CdnPrefixed', function($resource) {
  return $resource('/hpcapi/cdnprefixs/:id/', {id: '@id'});
})
.directive('contentProviderList', function(ContentProvider) {
  return {
    restrict: 'E',
    controllerAs: 'vm',
    templateUrl: '../../static/templates/contentProvider/cp_list.html',
    controller: function() {
      var _this = this;

      ContentProvider.query().$promise
      .then(function(cp) {
        _this.contentProviderList = cp;
      })
      .catch(function(e) {
        throw new Error(e);
      });
    }
  };
})
.directive('contentProviderDetail', function(ContentProvider, ServiceProvider, $routeParams) {
  return {
    restrict: 'E',
    controllerAs: 'vm',
    templateUrl: '../../static/templates/contentProvider/cp_detail.html',
    controller: function() {
      this.pageName = 'detail';
      var _this = this;

      if($routeParams.id) {
        ContentProvider.get({id: $routeParams.id}).$promise
        .then(function(cp) {
          _this.cp = cp;
        }).catch(function(e) {
          _this.result = {
            status: 0,
            msg: e.data.detail
          };
        });
      }

      ServiceProvider.query().$promise
      .then(function(sp) {
        _this.sp = sp;
      });

      // check if the list id match with item url
      this.activeServiceProvide = function(id, SPurl) {
        if(SPurl && SPurl.length > 0) {
          // take the last 2 char and remove trailing /
          return parseInt(SPurl.substr(SPurl.length - 2).replace('/','')) === id;
        }
        return false;
      };

      this.saveContentProvider = function(cp) {
        var p;

        if(cp.id) {
          p = cp.$update();
        }
        else {
          cp.name = cp.humanReadableName;
          p = new ContentProvider(cp).$save();
        }

        p.then(function() {
          _this.result = {
            status: 1,
            msg: 'Content Provider Saved'
          };
        })
        .catch(function(e) {
          _this.result = {
            status: 0,
            msg: e.data.detail
          };
        });
      };
    }
  };
})
.directive('contentProviderCdn', function($routeParams, CdnPrefixed, ContentProvider, lodash) {
  return{
    restrict: 'E',
    controllerAs: 'vm',
    templateUrl: '../../static/templates/contentProvider/cp_cdn_prefix.html',
    controller: function() {
      var _this = this;

      this.pageName = 'cdn';

      if($routeParams.id) {
        ContentProvider.get({id: $routeParams.id}).$promise
        .then(function(cp) {
          _this.cp = cp;
        }).catch(function(e) {
          _this.result = {
            status: 0,
            msg: e.data.detail
          };
        });
      }

      CdnPrefixed.query({contentProvider: $routeParams.id}).$promise
      .then(function(cp_prf) {
        _this.cp_prf = cp_prf;
      }).catch(function(e) {
        _this.result = {
          status: 0,
          msg: e.data.detail
        };
      });

      this.removePrefix = function(item) {
        item.$delete()
        .then(function() {
          lodash.remove(_this.cp_prf, item);
        })
        .catch(function(e) {
          _this.result = {
            status: 0,
            msg: e.data.detail
          };
        });
      };
    }
  };
})
.directive('contentProviderServer', function($routeParams) {
  return{
    restrict: 'E',
    controllerAs: 'vm',
    templateUrl: '../../static/templates/contentProvider/cp_origin_server.html',
    controller: function() {
      this.pageName = 'server';
      this.cp = {id: $routeParams.id};
    }
  };
})
.directive('contentProviderUsers', function($routeParams) {
  return{
    restrict: 'E',
    controllerAs: 'vm',
    templateUrl: '../../static/templates/contentProvider/cp_user.html',
    controller: function() {
      this.pageName = 'user';
      this.cp = {id: $routeParams.id};
    }
  };
});