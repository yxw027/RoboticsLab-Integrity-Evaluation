import numpy as np
from scipy.linalg import expm
import sys
sys.path.insert(0,'../functions/')
import pi_to_pi
import FG_fn
import R_NB_rot
import Q_BE_fn
import nearestNeighbor
import body2nav_3D
import math
import scipy.io as sio

class EstimatorClassEfkSim:

      landmark_map = None

      XX= np.zeros((15,1))
      x_true= np.zeros((3,1))
      alpha =  None # state of interest extraction vector
      PX= np.zeros((15,15))

      association =  None # association of current features
      association_full =  None # association of current features
      association_true =  None # only for simulation
      association_no_zeros =  None # association of associated features
      num_landmarks= 0  # nunber of landmarks in the map
      num_associated_lms= 0
      num_extracted_features  =  None
      num_of_extracted_features  =  None
      number_of_associated_LMs  =  None
      n_k =  None # number of absolute measurements at current time
      num_faults_k =  None # number of injected faults at current time
      gamma_k  =  None
      q_k  =  None
      Y_k  =  None
      H_k  =  None
      L_k  =  None
      Phi_k   =  None # state evolution matrix
      D_bar =  None # covariance increase for the state evolution
      T_d= 0  # detector threshold
      q_d= 0  # detector for the window of time
      initial_attitude =  None # save initial attitude for the calibration of IM?U biases
      appearances= np.zeros((1,300)) # if there are more than 300 landmarks, something's wrong
      FoV_landmarks_at_k =  None # landmarks in the field of view
      current_wp_ind= 1  # index of the sought way point
      goal_is_reached= 0
      steering_angle= 0
      lm_ind_fov =  None # indexes of the landmarks in the field of view
      M= 0 # preceding horizon size in epochs
      x_ph =  None # poses in the time window
      z_fg =  None # all the msmts in the time window
      z_lidar_ph =  None # lidar msmts in the ph
      z_lidar =  None # current lidar msmts
      z_gyro= 0  # current gyro msmt
      z_gyro_ph =  None # gyro msmts in the ph
      PX_prior =  None # cov matrix of the prior
      Gamma_prior =  None # information matrix of the prior
      m_M =  None # number of states to estimate
      n_total =  None # total numbe of msmts
      association_ph =  None # associations during the ph
      odometry_k =  None # odometry msmts at the current time
      odometry_ph =  None # velocity and steering angle for the ph
      x_prior =  None # stores x_{k-M} as a msmt for the next epoch
      n_L_k= 0 # number of associations at k
      n_L_M= 0 # number of associations in the ph
      H_k_gps =  None
      H_k_lidar =  None
      n_gps_k =  None
      n_L_k_ph =  None # number of associations in the ph
      eps = .1e-45


      def __init__(self, params):

          #initialize sizes differently for simulation
          self.XX = np.zeros((3,1))
          self.XX[params.ind_yaw]= np.deg2rad(params.initial_yaw_angle)
          self.x_true[params.ind_yaw]= np.deg2rad(params.initial_yaw_angle)
          self.PX = np.identity(3) * eps

          if (params.SWITCH_GENERATE_RANDOM_MAP) : #map generated by params
                self.landmark_map = params.landmark_map
                self.num_landmarks = shape(self.landmark_map,1)
          else: #map is loaded from saved variable
                data = sio.loadmat(join(params.path, 'landmark_map.mat'))     #needs to be concatenated differently?
                self.landmark_map = data.landmark_map
                self.num_landmarks = self.landmark_map.shape[0]

      # ----------------------------------------------
      # ----------------------------------------------
      def compute_alpha(self,params):
          self.alpha= np.array([[-sin( self.XX(params.ind_yaw) )]
                      [cos( self.XX(params.ind_yaw) )]
                       [0] ])
      # ----------------------------------------------
      # ----------------------------------------------
      def addNewLM(obj,z,R):

          # Number of landmarks to add
          n_L= z.shape[1];

          # update total number of landmarks
          self.num_landmarks= self.num_landmarks + n_L;

          # Add new landmarks to state vector
          z= body2nav_3D.body2nav_3D(z,self.XX[0:9]);
          zVector= np.transpose(z)
          zVector= zVector[:]
          tmp0 = XX.shape[0]
          tmp1 = XX.shape[1]
          XX = np.concatenate(XX,zVector)
          XX = np.reshape(XX,(tmp0+1,tmp1+2*n_L))

          spsi= math.sin(self.XX[8]);
          cpsi= math.cos(self.XX[8]);
          for i in range(n_L):
              ind= np.arange((15 + (2*i-1)),(15 + 2*i))

              dx= self.XX[ind[1]] - self.XX[1];
              dy= self.XX[ind[1]] - self.XX[1];

              H= np.array([[-cpsi, -spsi, -dx*spsi + dy*cpsi],[spsi,  -cpsi, -dx*cpsi - dy*spsi]])
              Y= H * self.PX[0:2,8] * np.transpose(H) + R

              tmp0 = PX.shape[0]
              tmp1 = PX.shape[1]
              PX = np.concatenate(PX,Y)
              PX = np.reshape(PX,(tmp0+1,tmp1+2))
      def compute_steering(obj,params):
          if (params.SWITCH_OFFLINE):
              xx = self.x_true
          else:
              xx = self.XX

          while (1):
              current_wp = params.way_points[:,self.current_wp_ind]
              d = math.sqrt((current_wp(1) - xx(1))**2 + (current_wp(2) - xx(2))**2)

              #check current distance to the waypoint
              if (d < params.min_distance_to_way_point):
                  self.current_wp_ind = self.current_wp_ind + 1

                  #reached final waypoint ----> flag and return
                  if (self.current_wp_ind > params.way_points.shape[1]):
                        self.goal_is_reached = 1
                        return
              else:
                    break
          #Compute change in G to point towards current waypoint
          delta_steering = pi_to_pi(np.arctan2(current_wp(1) - xx(1), current_wp(1) - xx(1) ) - xx(2))
          delta_steering = pi_to_pi(delta_steering - self.steering_angle)

          # limit rate
          max_delta = params.max_delta_steering * params.dt_sim
          if (abs(delta_steering) > max_delta):
              delta_steering = np.sign(delta_steering) * max_delta

          # limit angle
          self.steering_angle = pi_to_pi( self.steering_angle + delta_steering )
          if (abs(self.steering_angle) > params.max_steering):
              self.steering_angle = np.sign(self.steering_angle) * params.max_steering

      def get_gps_msmt(obj,params):
        #simulate measurement
        z = self.x_true[0:2] + np.random.multivariate_normal(zeros((2,1)),params.R_gps_sim)

      def get_lidar_msmt(obj,params):
        spsi = math.sin(self.x_true(3))
        cpsi = math.cos(self.x_true(3))
        z_lidar = []
        self.association_true = []
        self.num_faults_k = 0
        for l in np.arrange(self.num_landmarks):
            #check if the landmark is in the FoV
            dx = self.landmark_map(l,1) - self.x_true(1)
            if abs(dx) > params.lidarRange:
                continue
            dy = self.landmark_map(l,2) - self.x_true(2)
            if abs(dy) > params.lidarRange:
                continue
            if math.sqrt(dx^2 + dy^2) > params.lidarRange:
                continue

            # simulate msmt with noise
            z_lm[1] = dx * cpsi + dy * spsi + np.random.normal(0,params.sig_lidar)
            z_lm[2] = -dx * spsi + dy * cpsi + np.random.normal(0,params.sig_lidar)

            #add possible fault
            if params.SWITCH_LIDAR_FAULTS:
                if np.random.binomial(1,params.P_UA):
                    z_lm = z_lm + np.random.rand() * params.sig_lidar *10
                    self.num_faults_k = self.num_faults_k + 1

            #add measurement
            z_lidar = np.concatenate((z_lidar,z_lm), axis=0)

            #save the true association
            self.association_true =  np.concatenate((self.association_true,l), axis=0)

        #add them to the estimator class property
        self.z_lidar = z_lidar

        #if we use the NN association this values get overwritten
        self.n_L_k = size(self.association_true, axis=1)
        self.n_k = self.n_L_k * params.m_F

      def gps_update(self, z, R, params):

        n_L= ((self.XX).shape[0] - 15) / 2
        # if we are fast enough --> use GPS velocity msmt
        if (np.linalg.norm(z[3:6]) > params.min_vel_gps and params.SWITCH_GPS_VEL_UPDATE==1): # sense velocity
           R= np.diag( R )
           H = np.concatenate((np.eye(6), np.zeros((6,9)), np.zeros((6,int(n_L*2)))),axis=1)
           print('GPS velocity')

         # update only the position, no velocity
        else:
           z= z[0:3]
           R= np.diag( R[0:3] )
           H= np.concatenate((np.concatenate((np.eye(3), np.zeros((3,12))),axis = 1), np.zeros((3,int(n_L*2)))),axis = 1)
           print('-------- no GPS velocity ---------')

        self.XX[8]= pi_to_pi.pi_to_pi( self.XX[8] )
        L= np.dot( np.dot(self.PX, np.transpose(H)), np.linalg.inv( np.dot( np.dot(H, self.PX), np.transpose(H) ) + R) )
        innov= z - (np.dot( H, self.XX )).transpose()
        self.XX= self.XX + np.dot(L, innov.transpose())
        self.PX= self.PX - np.dot( np.dot(L, H), self.PX)

      def increase_landmarks_cov(self, minPXLM):

         if ((self.PX).shape[0] == 15):
            return 0
         PXLM= np.diag( self.PX[15:,15:] )
         minPXLM= minPXLM * np.ones((PXLM.shape[0],1));
         newDiagLM= max(PXLM,minPXLM);
         diffDiagLM= PXLM - newDiagLM;
         self.PX[15:,15:]= self.PX[15:end,15:end] - np.diag( diffDiagLM )

      def lidar_update(self,z,association,params):


        R= params.R_lidar;
        self.XX[8]= pi_to_pi.pi_to_pi( self.XX[8] );

        if np.all(association == -1):
           return 0

        # Eliminate the non-associated features
        ind_to_eliminate= association == -1 or association == 0;

        tmp_list = []
        check= np.shape(ind_to_eliminate)
        notScalar= len(check)
        if (notScalar == 0):
          if (ind_to_eliminate == 1):
             z=[]
             return 0
        else:
          for i in range(ind_to_eliminate.shape[0]):
              if (ind_to_eliminate[i] == 1):
                 tmp_list.append(i)
          z = np.delete(z,tmp_list,axis = 0)

        #z= np.delete(z,(ind_to_eliminate,:))
        association = np.delete(association,(ind_to_eliminate))

        # Eliminate features associated to landmarks that has appeared less than X times
        acc = 0
        ind_to_eliminate = []
        for i in association:  #ind_to_eliminate= self.appearances[association] <= params.min_appearances;
            if (self.appearances[i] <= params.min_appearances):
               ind_to_eliminate.append(1)
            else:
               ind_to_eliminate.append(0)
            acc = acc+1

        acc=0
        for i in ind_to_eliminate:    #z(ind_to_eliminate,:)= [];
            if z[acc] == 1:
               a = np.delete(a,acc,AXIS = 0)
            acc = acc+1

        acc = 0
        for i in ind_to_eliminate:    #association(ind_to_eliminate)= [];
            if i == 1:
               association= np.delete(association,acc)
            acc = acc+1


        # if no measurent can be associated --> return
        if isempty(z):
            return 0

        lenz= association.shape[0];
        lenx= self.XX.shape[0];

        R= np.kron( R,np.eye(lenz) );
        H= np.zeros((2*lenz,lenx));

        #Build Jacobian H
        spsi= sin(self.XX(9));
        cpsi= cos(self.XX(9));
        zHat= zeros(2*lenz,1);
        for i in range(association.shape[0]):
            # Indexes
            indz= 2*i + [-1,0];
            indx= 15 + 2*association[i] + [-1,0];

            dx= self.XX[indx[0]] - self.XX[0];
            dy= self.XX[indx[1]] - self.XX[1];

            # Predicted measurement
            zHat[indz]= np.array([[dx*cpsi + dy*spsi],[-dx*spsi + dy*cpsi]]);

            # Jacobian -- H
            H[indz,0]= np.array([[-cpsi],[ spsi]])
            H[indz,1]= np.array([[-spsi],[-cpsi]])
            H[indz,8]= np.array([[-dx * spsi + dy * cpsi],[-dx * cpsi - dy * spsi]]);
            H[indz,indx]= np.array([[cpsi, spsi],[-spsi, cpsi]]);


        # Update
        Y= H*self.PX*np.transpose(H) + R;
        L= self.PX * np.transpose(H) / Y;
        zVector= np.transpose(z)
        zVector= zVector[:];
        innov= zVector - zHat;

        # If it is calibrating, update only landmarks
        if (params.SWITCH_CALIBRATION ==1):
            XX0= self.XX[0:15];
            PX0= self.PX[0:15,0:15];
            self.XX= self.XX + L*innov;
            self.PX= self.PX - L*H*self.PX;
            self.XX[0:15]= XX0;
            self.PX[0:15,0:15]= PX0;
        else:
            self.XX= self.XX + L*innov;
            self.PX= self.PX - L*H*self.PX;

      def nearest_neighbor(self, z, params):

        n_F= z.shape[0];
        n_L= (self.XX.shape[0] - 15) / 2;
        association= np.ones((1,n_F)) * (-1);

        if (n_F == 0 or n_L == 0):
           return 0

        spsi= math.sin(self.XX[8]);
        cpsi= math.cos(self.XX[8]);
        zHat= np.zeros((2,1));
        # Loop over extracted features
        print(association)
        for i in range(1,n_F+1):
            minY= params.threshold_new_landmark;

            for l in range(1,n_L+1):
                ind= np.array[(15 + (2*l-1) - 1):(15 + 2*l)]

                dx= self.XX[ind[0]] - self.XX[0];
                dy= self.XX[ind[1]] - self.XX[1];

                zHat[0]=  dx*cpsi + dy*spsi;
                zHat[1]= -dx*spsi + dy*cpsi;
                gamma= np.transpose(z[i,:]) - zHat;

                H= np.array([[-cpsi, -spsi, -dx*spsi + dy*cpsi,  cpsi, spsi],
                    [spsi, -cpsi, -dx*cpsi - dy*spsi, -spsi, cpsi]]);

                Y= np.dot(np.dot(H,self.PX[[0,1,8,ind],[0,1,8,ind]]),np.transpose(H)) + params.R_lidar;

                y2= np.dot(np.dot(np.transpose(gamma),inv(Y)),gamma);

                if (y2 < minY):
                    minY= y2;
                    association[i-1]= l;

            # If the minimum value is very large --> new landmark
            if (minY > params.T_NN and minY < params.threshold_new_landmark):
                association[i-1]= 0;


        # Increase appearances counter
        for i in range(1,n_F+1):
            if (association[i-1] != -1 and association[i-1] != 0):
                self.appearances[association[i-1]-1]= self.appearances[association[i-1]-1] + 1;
        return association

      def odometry_update(self, params):
        # this function updates the estimate and true state for the given odometry
        # (velocity, steering angle) controls. Note that the the estimate is
        # updated with the computed controls, i.e. the ones we want to send to the
        # system. The true state is udpated with the actual controls executed in
        # the system, which have noise.


        # velocity & steering angle
        vel= params.velocity_sim;
        phi= self.steering_angle;

        # if it's the offline im analysis --> compute matrices and update true x
        if (params.SWITCH_OFFLINE==1):
            # compute state evolution matrix and its noise covariance matrix
            [self.Phi_k, self.D_bar]= self.return_Phi_and_D_bar(self.x_true, vel, phi, params);

        # if we are online --> add noise
        else:
            # compute state evolution matrix and its noise covariance matrix
            [self.Phi_k, self.D_bar]= self.return_Phi_and_D_bar(self.XX, vel, phi, params);

            # estimate state with computed controls
            self.XX= self.return_odometry_update(self.XX, np.array([[vel], [phi]]), params);

            # Add noise to the computed controls
            vel= vel +  np.random.normal(0, params.sig_velocity_sim);
            phi= phi +  np.random.normal(0, params.sig_steering_angle_sim);

        # True State
        self.x_true= self.return_odometry_update(self.x_true, np.array([[vel], [phi]]), params);

        # save the velocity and steering angle
        self.odometry_k= np.array([[vel], [phi]]);

      def  return_Phi_and_D_bar(self, x, vel, phi, params):
         # this function computes the state evolution matrix and its noise at the
         # corresponding time where the estimate is x and the odometry inputs are
         # vel and phi
         # compute variables
         s= math.sin(phi + x[params.ind_yaw-1]);
         c= cos(phi + x[params.ind_yaw-1]);
         vts= np.dot(np.dot(vel,params.dt_sim ),s);
         vtc= np.dot(np.dot(vel,params.dt_sim),c);

         # state evolution model jacobian
         Phi=np.array( [[1,0,-vts],
               [0,1,vtc],
               [0,0,1]])

         # controls jacobian (only steering angle and wheel velocity)
         Gu=np.array( [[params.dt_sim * c,                       -vts],
              [params.dt_sim * s,                        vtc],
              [params.dt_sim * sin(phi)/params.wheelbase_sim, np.dot(np.dot(np.dot(vel,params.dt_sim),math.cos(phi)),np.inv(params.wheelbase_sim))]]);

         # projection of controls uncertainty on the state (only steering angle and wheel velocity)
         D_bar= np.dot(np.dot(Gu,params.W_odometry_sim),np.transpose(Gu));

         return [Phi, D_bar]

      def return_odometry_update(self, x, u, params):
        # u: [velocity; steering angle]

        vel= u[0];
        phi= u[1];

        # True State
        x= [[x[0] + np.dot(np.dot(vel,params.dt_sim),math.cos(phi + x[2]))],
            [x[1] + np.dot(np.dot(vel,params.dt_sim),math.sin(phi + x[2]))],
            [pi_to_pi.pi_to_pi(x[2] + np.dot(np.dot(np.dot(vel,params.dt_sim),math.sin(phi))),np.inv( params.wheelbase_sim))]];
        return x
