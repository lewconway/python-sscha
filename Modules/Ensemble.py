# -*- coding: utf-8 -*-
import os
import numpy as np

import cellconstructor as CC
import cellconstructor.Structure
import cellconstructor.Phonons

"""
This source contains the Ensemble class
It is used to Load and Save info about the ensemble.
"""

class Ensemble:
    def __init__(self, dyn0, T0):
        """
        PREPARE THE ENSEMBLE
        ====================
        
        This method initializes and prepares the ensemble.
        
        NOTE: To now this works only in the gamma point (dyn0 must be a 1x1x1 supercell)
        
        Parameters
        ----------
            dyn0 : cellconstructor.Phonons.Phonons()
                This is the dynamical matrix used to generate the ensemble.
            T0 : float
                The temperature used to generate the ensemble.
        """
        
        # N is the number of element in the ensemble
        self.N = 0
        self.structures = []
        self.energies = []
        self.forces = []
        self.stresses = []
        
        self.sscha_energies = []
        self.sscha_forces = []
        
        # The original dynamical matrix used to generate the ensemble
        self.dyn_0 = dyn0
        self.T0 = T0
        
        # This is the weight of each configuration in the sampling.
        # It is updated with the update_weigths function
        self.rho = []
        self.current_dyn = dyn0
        
        self.current_T = T0
        
        self.q = []
        
    def load(self, data_dir, population, N):
        """
        LOAD THE ENSEMBLE
        =================
        
        This function load the ensemble from a standard calculation.
        
        The files need to be organized as follows
        
        data_dir / scf_populationX_Y.dat
        data_dir / energies_supercell_populationX.dat 
        data_dir / forces_populationX_Y.dat
        data_dir / pressures_populationX_Y.dat
        
        X = population
        Y = the configuration id (starting from 1 to N included, fortran convention)
        
        The files scf_population_X_Y.dat must contain the scf file of the structure.
        It should be in alat units, matching the same alat defined in the starting
        dynamical matrix.
        
        The energies_supercell.dat file must contain the total energy in Ry for
        each configuration.
        
        The forces_populationX_Y contains the 
        
        Parameters
        ----------
            data_dir : str
                The path to the directory containing the ensemble. If you used
                the fortran sscha.x code it should match the data_dir option of the
                input file.
            population : int
                The info to distinguish between several ensembles generated in the
                same data_dir. This also should match the correspective property
                of the fortran sscha.x input file.
            N : int
                The dimension of the ensemble. This should match the n_random
                variable from the fortran sscha.x input file.
        """
        A_TO_BOHR = 1.889725989
        
        # Check if the given data_dir is a real directory
        if not os.path.isdir(data_dir):
            raise IOError("Error, the given data_dir %s is not a valid directory." % data_dir)
        
        # Remove the tailoring slash if any
        if data_dir[-1] == "/":
            data_dir = data_dir[:-1]
        
        # Load the structures
        self.N = N
        
        self.forces = np.zeros( (self.N, self.dyn_0.structure.N_atoms, 3))
        self.stresses = np.zeros( (self.N, 3,3))
        
        self.sscha_energies = np.zeros(self.N)
        self.sscha_energies = np.zeros( (self.N, self.dyn_0.structure.N_atoms, 3))
        
        for i in range(self.N):
            # Load the structure
            structure = CC.Structure.Structure()
            structure.read_scf("%s/scf_population%d_%d.dat" % (data_dir, population, i+1), alat = self.dyn_0.alat)
            structure.has_unit_cell = True
            structure.unit_cell = self.dyn_0.structure.unit_cell
            
            # Load forces (Forces are in Ry/bohr, convert them in Ry /A)
            self.forces[i,:,:] = np.loadtxt("%s/forces_population%d_%d.dat" % (data_dir, population, i+1)) * A_TO_BOHR
            
            # Load stress
            self.stresses[i,:,:] =  np.loadtxt("%s/pressures_population%d_%d.dat" % (data_dir, population, i+1)) 
            
            # Setup the sscha energies and forces
            self.sscha_energies[i], self.sscha_forces[i,:,:] = self.dyn_0.get_energy_forces(structure)
            
        # Load the energy
        self.energies = np.loadtxt("%s/energies_supercell_population%d.dat" % (data_dir, population))
        
        # Setup the initial weight
        self.rho = np.ones(self.N)
        
        # Setup the sscha 
        
    def update_weights(self, new_dynamical_matrix, newT):
        """
        IMPORTANCE SAMPLING
        ===================
        
        
        This function updates the importance sampling for the given dynamical matrix.
        The result is written in the self.rho variable
        
        
        Parameters
        ----------
            new_dynamical_matrix : CC.Phonons.Phonons()
                The new dynamical matrix on which you want to compute the averages.
            new_T : float
                The new temperature.
        """
        
        self.current_T = newT
        for i in range(self.N):
            self.rho[i] = new_dynamical_matrix.GetRatioProbability(self.structures[i], newT, self.T0, self.dyn_0)
            self.sscha_energies[i], self.sscha_forces[i, :,:] = new_dynamical_matrix.get_energy_forces(self.structures[i])
            
            # Update also the q
            self.q[i]
            
        self.current_dyn = new_dynamical_matrix
        
    def get_effective_sample_size(self):
        """
        Get the Kong-Liu effective sample size with the given importance sampling.
        """
        
        return self.N * np.sum(self.rho) / float(np.sum(self.rho**2)) 
    
    def get_average_energy(self, subtract_sscha = False):
        """
        GET ENERGY
        ==========
        
        This is the average of the energy
        
        .. math::
            
            \\left< E\\right> = \\frac{1}{N} \\sum_{i = 1}^{N} E_i \\rho_i
            
            
        where :math:`\\rho_i` is the ratio between the probability of extracting the configuration $i$
        with the current dynamical matrix and with the dynamical matrix used to extract the ensemble.
        
        Parameters
        ----------
            subtract_sscha : bool, optional, default False
                If true, the average difference of energy respect to the sscha one is returned. This
                is good, because you can compute analytically the sscha energy and sum it on an infinite
                ensembe. Do in this way to suppress the stochastic noise.
        """
        
        if subtract_sscha:
            return np.sum( self.rho * (self.energies - self.sscha_energies)) / self.N
        return np.sum( self.rho * (self.energies)) / self.N
     
    def get_average_forces(self):
        """
        GET FORCES
        ==========
        
        This is the average of the forces that acts on the atoms
        
        .. math::
            
            \\left< \\vec F\\right> = \\frac{1}{N} \\sum_{i = 1}^{N}\\vec F_i \\rho_i
            
            
        where :math:`\\rho_i` is the ratio between the probability of extracting the configuration $i$
        with the current dynamical matrix and with the dynamical matrix used to extract the ensemble.
        """
        
        new_rho = np.tile(self.rho, (self.dyn_0.structure.N_atoms, 3, 1))
        return np.sum( new_rho  * (self.forces - self.sscha_forces)) / self.N
    
    def get_free_energy_gradient_respect_to_dyn(self):
        """
        FREE ENERGY GRADIENT
        ====================
        
        Get the free energy gradient respect to the dynamical matrix.
        
        .. math::
            
            \\nabla_\\Phi \\mathcal F = -\\sum_{a\\mu} \\left<\\gamma_\\mu^a q_\\mu\\right>
            
            \\gamma_\\mu^a = \\frac{e_\\mu^a \\nabla_\\Phi \\ln a_\\mu + \\nabla_\\Phi e_\mu^a}{\\sqrt M_a}(f_a - f^{\\Phi}_a)
            
            q_\\mu = \\sum_b \\sqrt M_b e_\\mu^b (R_b - \\mathcal R_b)
            
            \\nabla_\\Phi \\ln a_\\mu = \\frac{1}{2\\omega_\\mu a_\\mu} \\frac{\\partial a_\\mu}{\\partial\\omega_\\mu} \\frac{e_\\mu^a e_\\mu^b}{\\sqrt {M_aM_b}}
            
            \\nabla_\\Phi e_\mu^c  =\\sum_{\\nu \\neq \\mu} \\frac{e_\\nu^a e_\\mu^b}{\\sqrt {M_aM_b} (\\omega_\\mu^2 - \\omega_\\nu^2)} e_\\nu^c
    
    
        NOTE: it works only at gamma.
    
    
        Return
        ------
            A 3Nx3N matrix. The gradient of the free energy (To be symmetrized)
            
        """
        K_to_Ry=6.336857346553283e-06
        
        T = self.current_T
        # TODO: TO BE TESTED
        
        
        # Get the mass vector
        _m_ = np.zeros(self.dyn_0.structure.N_atoms * 3)
        for i in range(self.current_dyn.structure.N_atoms):
            _m_[ 3*i : 3*i + 3] = self.current_dyn.structure.masses[ self.current_dyn.structure.atom[i]]
        
        _m_sqrtinv = 1 / np.sqrt(_m_)
        
        # Get the frequency and polarization vector of the dynamical matrix
        w, pols = self.current_dyn.DyagDinQ(0)
        
        
        # TODO: improve the remove translations
        w = w[3:]
        pols = pols[:, 3:]
        
        n_modes = len(w)
        
        # Get the a_mu
        a_mu = np.zeros(n_modes)
        da_dw = np.zeros(n_modes)
        if T == 0:
            a_mu = 1 / np.sqrt(2* w) 
            da_dw = -1 /  np.sqrt(8 * w**3)
        else:            
            beta = 1 / (K_to_Ry*T)
            a_mu = 1 / np.sqrt( np.tanh(beta*w / 2) *2* w) 
            da_dw = - (w*beta + np.sinh(w*beta)) / (2 * np.sqrt(2) * w**2 * (np.cosh(beta*w) - 1) * np.sqrt(np.cosh(beta*w / 2) / (np.sinh(beta*w/2) * w)))
            
    
        # Prepare the w as a matrix
        _w_ = np.tile(w, (n_modes, 1))
        # 1 / (w_mu^2 - w_nu^2)
        one_over_omegamunu = 1 / (_w_**2 - _w_.transpose()**2)
        one_over_omegamunu *= 1 - np.eye(n_modes) # Remove the therms for mu equal to nu
        
                                        
        # Get the derivative of the lna_mu respect to the dynamical matrix
        # Inner product
        d_lna_d_dyn = np.einsum("i, ai, bi, ci, a, b, c->abic", da_dw/(2 * w * a_mu), pols, pols, pols, _m_sqrtinv, _m_sqrtinv, _m_sqrtinv)
        
        # Get the derivative respect to the polarization vector
        d_pol_d_dyn = np.einsum("ai,bj,ci,ji,a,b,c->abjc", pols, pols, pols, one_over_omegamunu, _m_sqrtinv, _m_sqrtinv, _m_sqrtinv)
        
        pre_sum = d_lna_d_dyn + d_pol_d_dyn
        
        # Get the q vector
        d_F_d_dyn = np.zeros(np.shape(self.current_dyn.dynmats[0]))
        for i in range(self.N):
            # Get the displacements of the structure
            u_disp = self.structures[i].get_displacements(self.current_dyn).reshape(3 * self.current_dyn.structure.N_atoms)
            
            # Get the forces on the configuration
            delta_f = (self.forces[i,:,:] - self.sscha_forces[i,:,:]).reshape(3 * self.current_dyn.structure.N_atoms)
            
            # Get the q vector
            q = np.einsum("i, ij, i", np.sqrt(_m_), pols, u_disp)
            
            # Get gamma matrix
            gamma = np.einsum("abcd, d", pre_sum, delta_f)
            
            # Contract the gamma matrix and multiply it for the weight
            d_F_d_dyn += - np.einsum("abc, c", gamma, q) * self.rho[i]
            
        # Normalization
        d_F_d_dyn /= np.sum(self.rho)
        
        #TODO: apply symmetries
            
        return d_F_d_dyn